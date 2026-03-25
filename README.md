# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Features

Algorithms and behaviors implemented in `pawpal_system.py` (and surfaced in `app.py` / `main.py`):

- **Greedy sequential scheduling** — `Scheduler.generate_plan` walks ranked tasks in order, places each on a single owner timeline starting at `rules["day_start"]` (default `08:00`), subtracts duration from remaining daily capacity, and pushes tasks that do not fit to `unscheduled_tasks` (no splitting or parallel tracks).
- **Sorting by time** — `sort_or_rank_tasks` orders feasible tasks using `_task_time_sort_key`: explicit `HH:MM` times first (by minutes from midnight), then named day parts (`morning`, `afternoon`, …), then tasks with no time signal last; ties break with required-before-optional, higher `priority_score`, shorter duration, then title.
- **Feasibility filtering** — `filter_feasible_tasks` drops completed tasks, task types listed in `owner.preferences["exclude_task_types"]`, and tasks whose `due_window` the owner cannot satisfy (`Owner.is_available`).
- **Cross-pet task queries** — `Owner.get_all_tasks` aggregates tasks from every pet for scheduling and filtering.
- **Task list filtering** — Module-level `filter_care_tasks` plus `Owner.filter_tasks` / `Pet.filter_tasks` narrow lists by completion flag and pet name (case-insensitive) without changing unrelated tasks.
- **Conflict warnings** — `detect_time_conflicts` / `has_time_conflicts` compare scheduled intervals in minute space with half-open ranges (touching end-to-start is not an overlap). `scheduling_conflict_warning` formats a UI-safe summary or `None` when there are no overlaps (malformed times yield a generic warning instead of crashing).
- **Plan explanations** — `DailyPlan.explain` and `Scheduler.build_explanations` produce human-readable text and per-task reasons for scheduled vs unscheduled outcomes.
- **Daily / weekly recurrence** — `CareTask.mark_complete` is idempotent; for `frequency` `daily` or `weekly`, it clones the next instance with `due_date` advanced by `timedelta` (1 or 7 days) and optionally `Pet.add_task` to queue it. Completed tasks are excluded from new plans.

Run `python main.py` for a terminal demo that exercises sorting, filtering, recurrence, and a sample overlap warning.

## 📸 Demo

Streamlit UI (`streamlit run app.py`): owner and pet registration, task list, scheduling preview (ranking and feasibility), and generated plan with timeline and explanations.

<a href="/Users/robelbruk/Dev/codepath/intro-to-ai/pawpal+/images/streamlit_demo.png" target="_blank"><img src="/Users/robelbruk/Dev/codepath/intro-to-ai/pawpal+/images/streamlit_demo.png" title="PawPal App" width="" alt="PawPal App" class="center-block" /></a>

## Testing PawPal+

Run the automated tests from the project root:

```bash
python -m pytest
```

The suite in `tests/test_pawpal.py` exercises core `pawpal_system` behavior: `CareTask.mark_complete` (including daily/weekly recurrence, idempotency, and non-recurring tasks), `filter_care_tasks` and owner-level task filtering, `Scheduler.sort_or_rank_tasks` (chronological ordering by time), `generate_plan` plus conflict detection (`detect_time_conflicts`, `has_time_conflicts`, duplicate and partial overlaps, adjacent non-overlapping slots), and `scheduling_conflict_warning` (including malformed times).

**Confidence Level:** ★★★★☆ (4/5) — Core scheduling, filtering, recurrence, and overlap logic are covered by passing unit tests; the Streamlit UI and full end-to-end flows are not automated here.

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.