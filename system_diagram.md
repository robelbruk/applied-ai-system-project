# PawPal+ system architecture (UML)

This diagram matches the classes and relationships in `pawpal_system.py`.

## What changed from the initial sketch

| Area | Earlier diagram | Final code |
|------|-----------------|------------|
| **Pet** | No `tasks` list or task APIs | `Pet` holds `CareTask` instances via `add_task` / `get_tasks` / `filter_tasks` |
| **Owner** | Basic fields only | Adds `get_pets`, `get_all_tasks` (union across pets), and `filter_tasks` |
| **CareTask** | Partial fields | Adds `time`, `frequency`, `due_date`, `is_completed`, `mark_complete`, `reset_completion` |
| **Scheduler** | Core plan + filter + sort | Adds conflict detection (`detect_time_conflicts`, `has_time_conflicts`, `scheduling_conflict_warning`) and private time/interval helpers |
| **New type** | — | `ScheduleConflict` pairs overlapping `PlanItem`s for validation / UI warnings |
| **Module** | — | `filter_care_tasks` is a shared function used by `Owner.filter_tasks` and `Pet.filter_tasks` |

## Class diagram (Mermaid)

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

## Export

The same diagram source is saved as `uml_final.mmd` for CLI rendering; the rendered image is `uml_final.png`.
