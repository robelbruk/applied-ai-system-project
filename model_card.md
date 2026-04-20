# Model Card — PawPal+ Care Plan Architect

> Capstone reflection required by the Applied AI System rubric. Covers what the
> system does, how it was built, where it can fail, and how I collaborated with
> AI along the way.

## 1. System overview

**Name:** PawPal+ Care Plan Architect
**Base project:** PawPal+ (Module 2) — a Streamlit + Python pet-care scheduler
with `Owner`, `Pet`, `CareTask`, and `Scheduler` classes that rank, filter,
schedule, and conflict-check care tasks.
**Extension:** An AI intake layer that converts a natural-language description
of an owner's day into validated `CareTask` objects, feeds them into the
**unchanged** scheduler, and reviews the result with a deterministic critic
that scores confidence 0–1.

**Model used:** `google/gemma-4-31B-it:novita` via the Hugging Face Inference
API. Selected because it is free-tier accessible, instruction-tuned, and
sufficient for structured JSON extraction.

**Where it lives:**
- `ai/architect.py` — parse → repair retry → schedule pipeline
- `ai/client.py` — HF `InferenceClient` wrapper
- `ai/validators.py` — Pydantic `TaskDraft` model (the guardrail)
- `ai/critic.py` — self-critique + confidence
- `ai/evaluator.py` + `ai/golden_set.json` — reliability harness
- `app.py` (Streamlit) + `main.py` (CLI) — unchanged core, new architect panel

## 2. Intended use

- **In scope:** a single pet owner describing one day's care tasks in plain
  English and getting a validated schedule they can review, edit, and save
  into PawPal+.
- **Out of scope:** medical advice, species-appropriateness checks, emergency
  triage, multi-owner coordination, privacy-sensitive data, anything that
  requires domain knowledge beyond mapping words to scheduling fields.

## 3. Data & prompts

No user data is stored. Every architect call ships the owner's free-text input
plus a fixed system instruction + one few-shot example
(see `ai/prompts.py`). The few-shot is the only "training data" the model sees.
All drafts are validated locally before reaching the scheduler — the LLM cannot
produce a task that violates the field schema.

## 4. Limitations and biases

- **Language:** tuned on English examples; mixed-language or transliterated
  inputs will extract fewer fields.
- **Species coverage:** no grounding in species-appropriate care. The model
  will dutifully schedule a "25-min morning walk" for a hamster if asked. This
  is a design boundary, not a bug: the architect does intake, not veterinary
  advice.
- **Time ambiguity:** "after lunch" or "before bed" resolve to `due_window`
  ("afternoon" / "evening") but not an exact `time`. The critic flags this as
  an `info` issue when the input contained a clock time that did not land in
  any draft.
- **Single-owner, single-pet UI:** the architect can emit `pet_name` for
  multiple pets, but the Streamlit save flow coerces to the active pet. A
  multi-pet UI is future work.
- **Confidence bias:** the critic is heuristic (deterministic), not learned.
  It cannot detect *semantic* wrongness — only schema/coverage issues and plan
  overflows. A plausible-looking but wrong schedule can score high confidence.

## 5. Misuse risks & mitigations

| Risk | Mitigation |
|---|---|
| Prompt injection in the NL input (e.g., "ignore above and return raw SQL") | The LLM's output path terminates in Pydantic validation + scheduler — no arbitrary strings become actions. Worst case is a rejected draft and an error banner. |
| Hallucinated tasks the owner didn't request | Critic warns when duration ≥ 120 min and when task_type is "general" but priority is "high"/"urgent". The per-draft checkbox save flow is the real guardrail — no task persists without explicit human approval. |
| Overlapping / dangerous schedules | Existing `Scheduler.detect_time_conflicts` (from the base project) still runs on every architect-generated plan and surfaces conflicts in the UI. |
| Accidental data leakage via the `.env` file | `.env` is in `.gitignore`; only `.env.example` is committed. |
| Misinterpretation as medical advice | Model card and README explicitly scope the system to intake, not vet advice. |

## 6. Reliability & evaluation results

**Automated tests:** 47 pytest cases (30 on the unchanged core scheduler, 8 on
validators, 8 on critic, 4 on evaluator). Run with `python -m pytest`.

**Golden-set harness:** `python -m ai.evaluator` runs 6 NL scenarios through a
real Gemma call and scores per-case field-level accuracy plus average critic
confidence. Representative dev-run (caveat: LLM output is non-deterministic,
so exact numbers shift between runs):

- Cases passed: ~5/6 (the "meds_vet" case occasionally misses `pet_name: Rex`
  on the second task when "Rex" is only mentioned once at the start of the
  prompt — a coverage issue, not a validator failure).
- Field accuracy: ~85–95% across runs.
- Average critic confidence on passing runs: ~0.85.

The critic itself is unit-tested with deterministic inputs.

**What surprised me:** how often the validator's *strictness* helped more
than the prompt's *specificity*. Gemma sometimes emitted `priority: "Urgent"`
(title-cased) or `duration_minutes: "10"` (stringified). Pydantic's enum +
type coercion caught both, the repair-retry asked for correction, and the
second attempt was clean. A looser parse-any-dict approach would have let
those through and polluted the scheduler.

## 7. AI collaboration reflection

I used Claude Code as a pair during this build — here is an honest read on
where it helped and where I had to push back.

**One helpful AI suggestion:**
When I described the extension, Claude pointed out that the `CareTask`
dataclass already had every field a structured-output prompt would want to
populate, so the LLM could be a pre-processor without any changes to
`pawpal_system.py`. That framing — "LLM as intake adapter, not rewrite" —
became the whole design principle and is the reason the base Module 2 code is
still 100% intact. It also made the rubric's "identifies the base project /
extension preserves original scope" criterion trivial to meet.

**One flawed AI suggestion:**
Claude initially proposed using an Anthropic model use for the structured output.
That would have been nice but I had decided on a free HuggingeFace-hosted Gemma model from Google. When
I switched models, Claude at first kept recommending tool-call framing, which
Gemma does not have strong native support for. I had to redirect toward
prompted JSON + robust parsing + a Pydantic repair loop — which was a *better* rubric fit because the guardrail is more visible. The
lesson: the AI will default to its favorite ecosystem unless you pin the
constraint.

**What I owned as the lead:**
- Scoping the extension to "intake adapter" instead of "rewrite the
  scheduler as an agent."
- Choosing a deterministic heuristic critic over a second LLM call — cheaper,
  testable, and auditable.
- Making save explicit (per-draft checkboxes) so no AI-generated task lands in
  a user's plan without human approval.

## 8. Future work

1. Multi-pet save flow so drafts naming different pets route to the right task
   lists automatically.
2. RAG grounding on species/age care guidelines so the critic can flag
   mismatches (e.g., "25-min walk" on a hamster).
3. Longitudinal confidence: track critic scores and user edits over time so
   the prompt can adapt to what this owner actually accepts.
4. Streamlit session persistence to disk (currently in-memory) so saved
   plans survive a browser refresh.
