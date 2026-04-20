# PawPal+ system architecture

This file documents the system at two levels:

1. **Applied-AI architecture** — the full capstone system: natural-language intake
   through the Care Plan Architect, into the unchanged core scheduler, through
   the critic, and out to the UI / CLI. Matches what is actually implemented in
   `ai/*` + `pawpal_system.py` + `app.py` + `main.py`.
2. **Class model (UML)** — the class-level view of `pawpal_system.py` carried
   over from the Module 2 base project. No core classes were modified for the
   capstone; every class and relationship below is still current.

The Mermaid source for the applied-AI flowchart is also saved as
`assets/architecture.mmd` so it can be rendered to PNG.

## 1. Applied-AI architecture (data flow)

```mermaid
flowchart LR
    classDef ai fill:#fef3c7,stroke:#b45309,color:#111
    classDef core fill:#e0f2fe,stroke:#0369a1,color:#111
    classDef ui fill:#ede9fe,stroke:#6d28d9,color:#111
    classDef eval fill:#dcfce7,stroke:#15803d,color:#111

    subgraph UI["UI / CLI"]
        direction TB
        ST["app.py (Streamlit):<br/>Describe your day -> Draft -> Save"]
        CLI["main.py (CLI demo)"]
    end

    subgraph ARCH["Care Plan Architect (ai/*)"]
        direction TB
        PR["prompts.py:<br/>system + few-shot (Gemma-friendly)"]
        CL["client.py:<br/>HF InferenceClient<br/>google/gemma-4-31B-it:novita"]
        AR["architect.py:<br/>parse -> retry -> run"]
        VA["validators.py:<br/>TaskDraft (Pydantic,<br/>enums + HH:MM + bounds)"]
        CR["critic.py:<br/>heuristic review +<br/>confidence score"]
    end

    subgraph CORE["Domain (pawpal_system.py) — unchanged"]
        direction TB
        OW["Owner"]
        PE["Pet"]
        CT["CareTask"]
        SC["Scheduler:<br/>filter + rank + generate_plan +<br/>detect_time_conflicts"]
        DP["DailyPlan / PlanItem /<br/>ScheduleConflict"]
    end

    subgraph EV["Evaluation"]
        direction TB
        GS["golden_set.json"]
        EVR["evaluator.py:<br/>per-case field diff +<br/>confidence summary"]
        TS["pytest suite<br/>(47 tests)"]
    end

    ST -->|NL text| AR
    CLI -->|NL text| AR
    AR --> PR
    AR --> CL
    CL -->|raw JSON| AR
    AR -->|draft dicts| VA
    VA -- invalid --> AR
    VA -- valid TaskDraft list --> AR
    AR -->|CareTask list| PE
    PE --> OW
    AR --> SC
    OW --> SC
    PE --> SC
    SC --> DP
    DP --> AR
    AR --> CR
    CR -->|CriticReport| AR
    AR -->|ArchitectTrace| ST
    AR -->|ArchitectTrace| CLI

    GS --> EVR
    EVR --> AR
    TS -.-> AR
    TS -.-> VA
    TS -.-> CR
    TS -.-> SC

    class ST,CLI ui
    class PR,CL,AR,VA,CR ai
    class OW,PE,CT,SC,DP core
    class GS,EVR,TS eval
```

### How to read this diagram

- **Purple (UI / CLI)** and **blue (core)** existed before the capstone. Blue is
  frozen — `pawpal_system.py` was not touched.
- **Amber (Care Plan Architect)** is the new AI layer. It sits *in front of* the
  scheduler: free-text goes in, `CareTask` objects come out, and the existing
  `Scheduler.generate_plan` runs exactly as it always has.
- **Green (Evaluation)** is the reliability layer: the golden set exercises the
  architect end-to-end, and the pytest suite unit-tests validators, critic, and
  scheduler. Dotted arrows are "tests target this module."
- The `VA -- invalid --> AR` edge is the repair-retry loop: Pydantic rejects
  malformed drafts before any `CareTask` is constructed.

## 2. Class model (UML)

### What changed from the initial sketch

| Area | Earlier diagram | Final code |
|------|-----------------|------------|
| **Pet** | No `tasks` list or task APIs | `Pet` holds `CareTask` instances via `add_task` / `get_tasks` / `filter_tasks` |
| **Owner** | Basic fields only | Adds `get_pets`, `get_all_tasks` (union across pets), and `filter_tasks` |
| **CareTask** | Partial fields | Adds `time`, `frequency`, `due_date`, `is_completed`, `mark_complete`, `reset_completion` |
| **Scheduler** | Core plan + filter + sort | Adds conflict detection (`detect_time_conflicts`, `has_time_conflicts`, `scheduling_conflict_warning`) and private time/interval helpers |
| **New type** | — | `ScheduleConflict` pairs overlapping `PlanItem`s for validation / UI warnings |
| **Module** | — | `filter_care_tasks` is a shared function used by `Owner.filter_tasks` and `Pet.filter_tasks` |

### Class diagram (Mermaid)

```mermaid
classDiagram
direction LR

class Owner {
  +name: str
  +available_minutes_per_day: int
  +preferences: dict
  +pets: Pet[*]
  +update_preferences(new_preferences)
  +is_available(time_slot) bool
  +get_daily_capacity() int
  +add_pet(pet)
  +get_pets() Pet[*]
  +get_all_tasks() CareTask[*]
  +filter_tasks(...) CareTask[*]
}

class Pet {
  +name: str
  +species: str
  +age: int
  +special_needs: list
  +tasks: CareTask[*]
  +requires_task_type(task_type) bool
  +get_care_profile() dict
  +add_task(task)
  +get_tasks() CareTask[*]
  +filter_tasks(...) CareTask[*]
}

class CareTask {
  +title: str
  +duration_minutes: int
  +priority: str
  +task_type: str
  +pet_name: str?
  +due_window: str?
  +time: str?
  +is_required: bool
  +frequency: str
  +due_date: Date?
  +is_completed: bool
  +priority_score() int
  +fits_in(remaining_minutes) bool
  +describe() str
  +mark_complete(...) CareTask?
  +reset_completion()
}

class Scheduler {
  +owner: Owner
  +pet: Pet
  +tasks: CareTask[*]
  +rules: dict
  +generate_plan(date) DailyPlan
  +filter_feasible_tasks() CareTask[*]
  +sort_or_rank_tasks() CareTask[*]
  +build_explanations(plan) dict
  +detect_time_conflicts(plan) ScheduleConflict[*]
  +has_time_conflicts(plan) bool
  +scheduling_conflict_warning(plan) str?
  ~_add_minutes(start, minutes) str
  ~_hhmm_to_minutes(hhmm) int
  ~_plan_item_interval_minutes(item) tuple
  ~_plan_items_time_overlap(a, b) bool
}

class DailyPlan {
  +date: DateType
  +scheduled_items: PlanItem[*]
  +unscheduled_tasks: CareTask[*]
  +add_item(task, start_time, end_time, reason)
  +total_minutes() int
  +remaining_time(owner_capacity_minutes) int
  +to_display_rows() dict[*]
  +explain() str
}

class PlanItem {
  +task: CareTask
  +start_time: str
  +end_time: str
  +reason: str
  +duration() int
  +to_dict() dict
}

class ScheduleConflict {
  <<frozen dataclass>>
  +first: PlanItem
  +second: PlanItem
}

class filter_care_tasks {
  <<module function>>
  +filter_care_tasks(tasks, ...) CareTask[*]
}

Scheduler --> Owner : uses
Scheduler --> Pet : uses
Scheduler --> CareTask : ranks / filters
Scheduler --> DailyPlan : creates
Scheduler ..> ScheduleConflict : detect_time_conflicts

DailyPlan *-- PlanItem : contains
PlanItem --> CareTask : references
DailyPlan --> CareTask : unscheduled
ScheduleConflict --> PlanItem : pairs

Owner "1" o-- "*" Pet : owns
Pet "1" *-- "*" CareTask : tasks

Owner ..> filter_care_tasks : filter_tasks
Pet ..> filter_care_tasks : filter_tasks
filter_care_tasks ..> CareTask : filters
```

_Sorting uses module helper `_task_time_sort_key` (not shown) inside `sort_or_rank_tasks`._

### Export

The same UML diagram source is saved as `uml_final.mmd` for CLI rendering; the
rendered image is `images/uml_final.png`. The applied-AI flowchart source is in
`assets/care-plan-architect.png`.
