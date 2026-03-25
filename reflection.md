# PawPal+ Project Reflection

## 1. System Design
- Core User Actions
    - Enter basic owner + pet info
    - Add/edit care tasks (with at least duration and priority)
    - Generate a daily schedule/plan based on constraints and priorities

**a. Initial design**

- Briefly describe your initial UML design.
  - My initial UML used six classes: `Owner`, `Pet`, `CareTask`, `Scheduler`, `DailyPlan`, and `PlanItem`. I separated "data holder" classes (`Pet`, `CareTask`, `PlanItem`) from orchestration/output classes (`Scheduler`, `DailyPlan`) so scheduling logic stayed centralized instead of scattered.
- What classes did you include, and what responsibilities did you assign to each?
  - `Owner`: stores owner-level constraints (name, available daily minutes, preferences) and provides availability/capacity helpers.
  - `Pet`: stores pet profile data (name, species, age, special needs) and exposes methods that describe care requirements.
  - `CareTask`: represents one care action with duration, priority, type, and scheduling metadata.
  - `Scheduler`: orchestrates filtering feasible tasks, ranking tasks, and generating a `DailyPlan`.
  - `DailyPlan`: stores one day's output, including scheduled and unscheduled tasks, plus display/explanation helpers.
  - `PlanItem`: models one scheduled entry (task + time range + reason) so each scheduled decision is explicit and explainable.

**b. Design changes**
- Did your design change during implementation?
    - Yes. I made two design updates after reviewing the skeleton
- If yes, describe at least one change and why you made it.
    - I added `Owner.pets` and an `add_pet()` method to explicitly model the owner-to-pet relationship instead of assuming a single pet forever.
    - I added `CareTask.pet_name` so tasks can be tied to a specific pet, which prevents ambiguity if the app expands to multi-pet scheduling.
    - I removed `DailyPlan.total_minutes` as a stored field and replaced it with a `total_minutes()` method to avoid state drift between `scheduled_items` and a manually maintained total.
    - These changes make the model safer to evolve and reduce avoidable consistency bugs in scheduling logic.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
  - **Owner capacity:** total minutes available per day (`Owner.get_daily_capacity`), consumed as tasks are placed sequentially.
  - **Task feasibility:** completed tasks are skipped; `owner.preferences["exclude_task_types"]` can drop whole categories; if a task has a `due_window`, the owner must be available for that slot (`Owner.is_available`).
  - **Ranking order:** after feasibility, tasks are sorted by time signal (`_task_time_sort_key`: clock `HH:MM`, then day-part labels like morning/evening, then untimed tasks), then required before optional, then higher `priority_score`, then shorter duration, then title for stable ties.
  - **Single timeline:** `generate_plan` starts at `rules["day_start"]` (default `08:00`) and chains tasks back-to-back until capacity runs out; leftovers go to `unscheduled_tasks`.

- How did you decide which constraints mattered most?
  - **Feasibility first** — there is no point ordering tasks that should never run today (completed, excluded type, or impossible window).
  - **Time hints second** — matching “morning” before “evening” makes the plan feel like a real day.
  - **Priority and duration** — break ties in a way that favors urgent work and packs smaller tasks when scores tie, which fits the greedy layout.

**b. Tradeoffs**

- **Describe one tradeoff your scheduler makes.**

  - The main tradeoff is **sequential single-line scheduling**: `generate_plan` walks the ranked task list and places each task **immediately after** the previous one on **one** owner timeline (`day_start` → …). It does not allocate **parallel** tracks (e.g., two pets at once with help, or overlapping real-world windows). That keeps the implementation small and the output easy to read, but it **forces a strict order** and may **serialize** work that could overlap in practice. (Note: **conflict detection** is different—it compares **intervals** (`start`–`end`) and flags **overlapping durations**, not “exact same timestamp” only; half-open ranges mean **back-to-back** slots are not treated as conflicts. The default generator never produces overlaps, so that check is mainly for **manual or merged** plans.)

- **Why is that tradeoff reasonable for this scenario?**
  - For this project, **one owner** and **one daily minute budget** are the core constraints; a single ordered queue matches that story and is straightforward to test and print. A richer model (parallel resources, travel time, multiple caregivers) would be better for production but is heavier than needed here.

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
  - I used AI for **brainstorming** class boundaries and naming, **drafting** docstrings and repetitive tests, **spot-checking** edge cases (e.g. interval overlap rules, midnight wrap), and **refactoring** when I wanted cleaner names without changing behavior.
- What kinds of prompts or questions were most helpful?
  - Prompts that **named the file and function** and asked for behavior **without** rewriting architecture (“explain how half-open intervals apply to `PlanItem` times”) worked better than open-ended “write my scheduler” requests.
  - Asking for **pytest cases** from a short scenario (“two tasks, overlapping times, expect one conflict”) was faster than writing assertions from scratch.

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
  - Copilot Chat once suggested **folding conflict detection into `DailyPlan` as a method** so every plan would “know” if it conflicted. I **rejected** that as the main design: overlap logic depends on parsing `HH:MM` and comparing intervals—those are **scheduler concerns** (and validation), while `DailyPlan` should stay a **container + presentation** (`explain`, `to_display_rows`). I kept **`detect_time_conflicts` and `scheduling_conflict_warning` on `Scheduler`** so the domain model stays clear: “plan” is data; “scheduler” is the engine that builds and inspects plans.
- How did you evaluate or verify what the AI suggested?
  - I **ran** `pytest` after every change that touched scheduling, and I **reread** the half-open overlap rule in code so the AI’s English explanation matched the implementation. If a suggestion didn’t have a clear test hook, I treated it as optional.

### VS Code Copilot: AI strategy

**Which Copilot features were most effective for building your scheduler?**

- **Inline completions (Ghost Text)** — best for **boilerplate** (`dataclass` fields, `sorted(..., key=lambda ...)`, test `assert` blocks) and for **sticking to my own patterns** once I had written one example method.
- **Copilot Chat** — best for **short explanations** of tricky code (e.g. why `end <= start` adjusts by 24 hours in interval math) and for **drafting a test list** I then trimmed to match `pytest` style.
- **“Generate tests” / test-focused prompts** — useful as a **starting point** for parametrized edge cases, but I always **edited** expectations to match the real API (`Scheduler`, `CareTask.mark_complete` signatures).

**Give one example of an AI suggestion you rejected or modified to keep your system design clean.**

- Same as above: I **did not** move conflict detection onto `DailyPlan` as a fat model. I kept overlap detection on **`Scheduler`** and left **`DailyPlan`** responsible for **aggregating** `PlanItem`s and **text** output. That preserved a single place for “how do we interpret times?” and avoided mixing validation with display.

**How did using separate chat sessions for different phases help you stay organized?**

- **Phase 1 (UML / domain model):** one thread with **no code**—only classes, relationships, and naming—so I didn’t drift into implementation details.
- **Phase 2 (core logic):** a fresh thread focused on **`pawpal_system.py`** and tests, so prompts didn’t pull in Streamlit noise.
- **Phase 3 (UI):** another thread for **`app.py`**, so suggestions were Streamlit-specific (`st.table`, `st.session_state`) and didn’t rewrite backend contracts.
- **Phase 4 (packaging / README / diagram):** short sessions for **documentation accuracy**, not behavior changes. Starting new chats kept **context windows** focused and reduced “fix the UI” answers when I was asking about **ranking keys**.

**Summarize what you learned about being the "lead architect" when collaborating with powerful AI tools.**

- The model is **fast at volume** but **agnostic to your product boundaries** unless you state them. Being the lead architect means **owning the seams**: which class owns which behavior, what is **tested** vs **assumed**, and when to **say no** to a clever refactor that blurs layers. AI tools are strong **implementers and sparring partners**; they are not substitutes for **requirements, acceptance criteria, and verification**—those stay on you.

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
  - **`CareTask.mark_complete`:** idempotency, daily vs weekly `due_date` advancement, `pet.add_task` for the next instance, non-recurring frequencies.
  - **`filter_care_tasks` / owner filtering:** completion and pet-name filters.
  - **`sort_or_rank_tasks`:** chronological ordering when `time` differs.
  - **`generate_plan`:** capacity limits, unscheduled overflow.
  - **Conflicts:** `detect_time_conflicts`, `has_time_conflicts`, `scheduling_conflict_warning`—duplicate overlaps, partial overlaps, adjacent non-overlapping slots, malformed times (warning path).
- Why were these tests important?
  - They lock down **deterministic ranking**, **recurrence rules**, and **interval math**—the places bugs hide without a human staring at a calendar. UI tests are manual; **unit tests** give confidence the engine is right before wiring Streamlit.

**b. Confidence**

- How confident are you that your scheduler works correctly?
  - **High for the behaviors covered by tests** (ranking, feasibility, plan generation, overlap detection, recurrence). **Lower for end-to-end flows** in the browser (session state, multi-step clicks) because those are not automated here.
- What edge cases would you test next if you had more time?
  - **Multi-pet** schedules with tasks on different pets and **shared** capacity.
  - **Preference edge cases:** empty `exclude_task_types`, availability dict with `False` for a slot.
  - **Property-style** checks: greedy generator never produces overlapping items (invariant).

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?
  - The **clear split** between `DailyPlan` / `PlanItem` (what we show) and `Scheduler` (how we build and validate), plus **tests** that encode the trickiest rules (overlap, recurrence).

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?
  - **Richer reasons** on each `PlanItem` (today the reason string is generic), and **optional** UI controls for `day_start` and excluded types so the Streamlit demo exercises **preferences** without code edits.

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?
  - **Small, testable modules beat “smart” monoliths**—and AI accelerates coding **when** you already know the boundaries you want; the hard part is still **deciding** those boundaries and **proving** them with tests.
