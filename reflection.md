# PawPal+ Care Plan Architect — Capstone Reflection

> This reflection covers the **Applied AI System capstone**: extending my
> Module 2 PawPal+ scheduler with a natural-language intake layer (the
> Care Plan Architect). For scope, limits, biases, misuse, and model-level
> details, see `model_card.md`. This file is about the **process** — how the
> extension was designed, where AI collaboration helped or misled, what I
> tested, and what I learned as the lead architect.

## 1. System Design (extension)

**a. Initial design**

- What did I start from, and what did I add?
  - I started from the Module 2 PawPal+ scheduler (`pawpal_system.py`) and
    **did not modify any of its classes**. The extension is a new `ai/`
    package with five modules: `prompts`, `client`, `validators`,
    `architect`, `critic`, plus `config` for env loading and `evaluator`
    + `golden_set.json` for testing.
  - The design principle was **"LLM as intake adapter, not rewrite."**
    The architect sits *in front of* `Scheduler.generate_plan`: natural
    language goes in, validated `CareTask` objects come out, and the
    original greedy scheduler runs exactly as it always has.
- Which components are new, and where do they sit in the data flow?
  - `ai/architect.py`: orchestrates `parse → Pydantic validate →
    repair-retry (once) → attach to Pet → call Scheduler → critic review`.
  - `ai/validators.py`: a Pydantic `TaskDraft` model with enums
    (priority / task_type / frequency / due_window), `1 ≤ duration ≤ 240`,
    and an `HH:MM` regex. This is the real guardrail — the LLM cannot emit
    a task that violates the schema and reach the scheduler.
  - `ai/client.py`: a thin wrapper around the Hugging Face
    `InferenceClient`, pinned to `google/gemma-4-31B-it:novita`.
  - `ai/critic.py`: a **deterministic** heuristic reviewer that scores
    confidence 0–1 and flags coverage/plan issues as `info` / `warning` /
    `error`.
  - `ai/trace.py`: an `ArchitectTrace` dataclass that records every stage
    so the UI can show *what happened* even when a later step failed.

**b. Design changes**

- Did the design change during implementation?
  - Yes — three changes worth calling out.
- What changed and why?
  - I added a **`.env` + `ai/config.py`** setup after Phase 1 so `HF_TOKEN`
    could live in an ignored file instead of the shell. `python-dotenv`
    loads it on `import ai`, and real shell vars still win (`override=False`)
    so CI secrets work.
  - I moved the Streamlit **preview rendering out of the button click block**
    and persisted the `ArchitectTrace` in `st.session_state`. This unlocked
    the per-draft **Save / Discard** flow — without it, a draft couldn't
    survive the script rerun that Streamlit triggers on every button click.
  - I **coerced `draft.pet_name` to the active pet on save**. The architect
    can emit names for multiple pets (Buddy, Mochi), but the current UI is
    single-pet, and silent coercion is less surprising than a failure path.

## 2. AI Feature and Tradeoffs

**a. Structured prompting + Pydantic over native tool use**

- Why this path?
  - Gemma does not have strong native tool-use fine-tuning. Pretending it
    does would have made the prompt brittle and the failure modes
    invisible. Prompted JSON + strict Pydantic + a **visible repair
    retry** puts the reliability story in the foreground, which is also a
    better fit for the rubric's "reliability/guardrail component" criterion.
- What is the tradeoff?
  - I lose provider-native schema enforcement (which a tool-use API can
    give you) and pay that back in parsing code: markdown-fence stripping,
    object extraction from prose, `{"tasks": [...]}` vs bare-list handling.
    That code is short and tested, and the upside is that swapping Gemma
    for any chat-completion-compatible model is a one-line change in
    `client.py`.

**b. Heuristic critic over a second LLM call**

- Why this path?
  - A second LLM critic would be slower, more expensive, non-deterministic,
    and harder to unit-test. A heuristic critic is cheap, each deduction
    traces to a named check (empty drafts → error, short input → warning,
    unscheduled tasks → warning, clock-time/pet coverage → info), and the
    confidence score is reproducible for the same input.
- What does the heuristic critic **not** catch?
  - Semantic wrongness. A plausible-looking but wrong schedule can still
    score high confidence. That is why the Streamlit save flow requires
    **explicit per-draft human approval** — the critic is advisory; the
    checkbox is the trust boundary.

## 3. AI Collaboration

**a. How I used Claude Code across phases**

- Phase 1 (scaffolding): I gave Claude the repo and asked for an audit
  before any code — file-by-file breakdown, extension options ranked by
  rubric fit and demo quality. That planning conversation shaped the
  "intake adapter" scoping decision I kept throughout.
- Phase 2 (reliability): I directed Claude to build the critic
  *deterministically* instead of as a second LLM call, and to wire a
  golden-set evaluator with field-level diffs. I also asked for the
  per-draft save flow and specified the session-state mechanics so the
  Streamlit rerun loop would behave.
- Phase 3 (docs): Claude drafted the README, model card, and flowchart
  Mermaid; I edited for voice and trimmed overclaiming.

**b. Judgment and verification**

- One helpful AI suggestion I accepted: Claude pointed out that the
  existing `CareTask` dataclass already had every field a structured-output
  prompt would want (`title`, `duration_minutes`, `priority`, `task_type`,
  `pet_name`, `due_window`, `time`, `is_required`, `frequency`). That
  observation was the reason I could freeze `pawpal_system.py` instead of
  rewriting it — a one-line insight that shaped the whole project.
- One flawed AI suggestion I rejected: after I specified a free
  HuggingFace-hosted Gemma model, Claude kept suggesting Anthropic-style
  tool-use framing for the structured output. Gemma does not support that
  well, and retrofitting it would have been fragile. I redirected toward
  prompted JSON + Pydantic + repair-retry, which is honestly a stronger
  rubric fit because the guardrail is more visible. Lesson: the model
  defaults to its favorite ecosystem unless you pin the constraint.
- How I verified suggestions were correct: I ran `python -m pytest` after
  every code change (47 tests, all passing at every phase boundary) and I
  kept the Streamlit UI running in a second terminal to sanity-check the
  save flow interactively. When Claude wrote docstrings or README claims,
  I re-read the code it was describing and removed anything that was
  aspirational rather than implemented.

## 4. Testing and Verification

**a. What I tested**

- **Unchanged core (30 tests)**: carried over from Module 2 —
  `CareTask.mark_complete` (daily / weekly / once / idempotent),
  `filter_care_tasks`, `sort_or_rank_tasks`, `generate_plan`,
  `detect_time_conflicts`, `scheduling_conflict_warning`.
- **Validators (8 tests)**: `TaskDraft` rejects bad priority, bad
  task_type, duration out of range, malformed time; normalizes time
  padding (`8:05 → 08:05`); `TaskDraftList` rejects missing fields.
- **Architect (10 tests)**: parse clean JSON, strip markdown fences,
  extract JSON from prose, accept bare list, reject invalid duration;
  run end-to-end with a mocked LLM to assert pet attachment and plan
  generation; retry once on bad first response; record an error when
  both attempts fail; reject invalid enum from both attempts.
- **Critic (8 tests)**: empty drafts give 0.0 and an error; clean input
  gives ≥ 0.9; unscheduled tasks and conflict warning downgrade to
  warning band; unmentioned pet / missed clock time flag info issues;
  short input flags warning; `Issue` is hashable.
- **Evaluator (4 tests)**: exact match passes; wrong duration fails;
  missing matching title fails; case-id filtering works — all with a
  mocked LLM so the unit suite stays offline.
- **Golden-set harness**: `python -m ai.evaluator` runs six NL cases
  through a real Gemma call and prints per-case field-level accuracy,
  overall pass rate, and average critic confidence.

**b. Confidence**

- **High** for the schema/guardrail layer: Pydantic, repair retry, and
  conflict detection are deterministic and covered by unit tests.
- **Medium** for the end-to-end NL-to-plan path: the golden-set passes
  around 5/6 cases on typical runs with 85–95% field accuracy, and the
  failing case is usually a pet-name coverage issue, not a structural
  bug.
- **Lower** for edge cases the suite does not yet cover: adversarial
  prompts that try prompt injection, very long inputs, mixed-language
  inputs, and multi-pet disambiguation in the UI.

## 5. Reflection

**a. What went well**

- The **strict separation** between the AI layer and the core. Every
  promise I made about "the scheduler is unchanged" is literally true —
  47 tests still pass, 30 of them against pre-capstone code I did not
  touch. That made documentation honest and demos believable.
- The **critic + Pydantic pairing**. Early Gemma runs emitted
  `priority: "Urgent"` (title-cased) and `duration_minutes: "10"`
  (stringified). I initially expected to solve this with better prompts
  but the validator caught it on the first pass and the repair retry
  cleaned it up on the second. Being *strict early* was cheaper than
  being *smart later*.

**b. What I would improve**

- **Multi-pet save flow** — the architect can already emit multiple
  `pet_name` values, but the Streamlit UI collapses them to the active
  pet. Building a proper pet selector and per-pet routing would remove
  one of my larger caveats.
- **Semantic critic** — a lightweight species/age grounding (even a
  small static rules file, before full RAG) would let the critic flag
  "25-min walk for a hamster" instead of treating it as plausible.
- **Persistent storage** — saved plans currently live in
  `st.session_state` and are lost on refresh. Swapping to SQLite would
  be small and would make the demo feel more real.

**c. Key takeaway**

- **Your validators are your trust boundary.** The LLM is fast and
  flexible; the strict things around it (Pydantic schema, deterministic
  critic, per-draft human approval, conflict detection inherited from
  the original scheduler) are what make the output safe to act on. As
  the lead architect, my job was less about prompting the model well
  and more about **designing the seams** that catch it when it is
  wrong — and then **leaving the human in the loop** for everything
  those seams cannot prove.
