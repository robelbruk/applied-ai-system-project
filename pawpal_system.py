from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as DateType
from typing import Any, Dict, List, Optional


class Owner:
    def __init__(
        self,
        name: str,
        available_minutes_per_day: int,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize an owner with availability, preferences, and pets."""
        self.name = name
        self.available_minutes_per_day = available_minutes_per_day
        self.preferences: Dict[str, Any] = preferences or {}
        self.pets: List[Pet] = []

    def update_preferences(self, new_preferences: Dict[str, Any]) -> None:
        """Update owner preferences with new values."""
        self.preferences.update(new_preferences)

    def is_available(self, time_slot: str) -> bool:
        """Return whether owner is available during the given time slot."""
        availability = self.preferences.get("availability")
        if availability is None:
            return True
        if isinstance(availability, dict):
            return bool(availability.get(time_slot, True))
        if isinstance(availability, (list, tuple, set)):
            return time_slot in availability
        return bool(availability)

    def get_daily_capacity(self) -> int:
        """Return total available minutes for the day."""
        return max(0, int(self.available_minutes_per_day))

    def add_pet(self, pet: Pet) -> None:
        """Attach a pet to this owner profile."""
        if pet not in self.pets:
            self.pets.append(pet)

    def get_pets(self) -> List[Pet]:
        """Return all pets linked to this owner."""
        return list(self.pets)

    def get_all_tasks(self) -> List[CareTask]:
        """Collect all tasks from every pet."""
        all_tasks: List[CareTask] = []
        for pet in self.pets:
            all_tasks.extend(pet.get_tasks())
        return all_tasks


@dataclass
class Pet:
    name: str
    species: str
    age: int
    special_needs: List[str] = field(default_factory=list)
    tasks: List[CareTask] = field(default_factory=list)

    def requires_task_type(self, task_type: str) -> bool:
        """Return True if this pet requires the provided task type."""
        normalized = task_type.strip().lower()
        return any(need.strip().lower() == normalized for need in self.special_needs)

    def get_care_profile(self) -> Dict[str, Any]:
        """Return normalized pet care details used by scheduling logic."""
        return {
            "name": self.name,
            "species": self.species,
            "age": self.age,
            "special_needs": list(self.special_needs),
            "task_count": len(self.tasks),
        }

    def add_task(self, task: CareTask) -> None:
        """Add a care task to this pet."""
        if task.pet_name is None:
            task.pet_name = self.name
        self.tasks.append(task)

    def get_tasks(self) -> List[CareTask]:
        """Return this pet's tasks."""
        return list(self.tasks)


@dataclass
class CareTask:
    title: str
    duration_minutes: int
    priority: str
    task_type: str
    pet_name: Optional[str] = None
    due_window: Optional[str] = None
    is_required: bool = False
    frequency: str = "daily"
    is_completed: bool = False

    def priority_score(self) -> int:
        """Convert priority label to numeric value."""
        priority_map = {
            "low": 1,
            "medium": 2,
            "high": 3,
            "urgent": 4,
        }
        return priority_map.get(self.priority.strip().lower(), 1)

    def fits_in(self, remaining_minutes: int) -> bool:
        """Return True if task duration fits in remaining minutes."""
        return self.duration_minutes <= remaining_minutes

    def describe(self) -> str:
        """Return a user-friendly description of the task."""
        parts = [f"{self.title} ({self.duration_minutes} min)"]
        if self.pet_name:
            parts.append(f"for {self.pet_name}")
        if self.due_window:
            parts.append(f"during {self.due_window}")
        parts.append(f"[{self.priority}]")
        if self.is_completed:
            parts.append("completed")
        return " ".join(parts)

    def mark_complete(self) -> None:
        """Mark this task as completed."""
        self.is_completed = True

    def reset_completion(self) -> None:
        """Mark this task as not completed."""
        self.is_completed = False


@dataclass
class PlanItem:
    task: CareTask
    start_time: str
    end_time: str
    reason: str

    def duration(self) -> int:
        """Return task duration in minutes."""
        return self.task.duration_minutes

    def to_dict(self) -> Dict[str, Any]:
        """Serialize this plan item for display."""
        return {
            "task": self.task.title,
            "pet": self.task.pet_name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_minutes": self.duration(),
            "reason": self.reason,
        }


@dataclass
class DailyPlan:
    date: DateType
    scheduled_items: List[PlanItem] = field(default_factory=list)
    unscheduled_tasks: List[CareTask] = field(default_factory=list)

    def add_item(self, task: CareTask, start_time: str, end_time: str, reason: str) -> None:
        """Append a scheduled plan item."""
        self.scheduled_items.append(
            PlanItem(task=task, start_time=start_time, end_time=end_time, reason=reason)
        )

    def total_minutes(self) -> int:
        """Return the total scheduled minutes for this plan."""
        return sum(item.duration() for item in self.scheduled_items)

    def remaining_time(self, owner_capacity_minutes: int) -> int:
        """Return remaining minutes given the owner's daily capacity."""
        return max(0, owner_capacity_minutes - self.total_minutes())

    def to_display_rows(self) -> List[Dict[str, Any]]:
        """Convert plan items to tabular rows for UI."""
        return [item.to_dict() for item in self.scheduled_items]

    def explain(self) -> str:
        """Return a human-readable explanation of the schedule."""
        lines: List[str] = [f"Plan for {self.date.isoformat()}:"]
        if not self.scheduled_items:
            lines.append("No tasks were scheduled.")
        else:
            for item in self.scheduled_items:
                lines.append(
                    f"- {item.start_time}-{item.end_time}: {item.task.title} ({item.reason})"
                )
        if self.unscheduled_tasks:
            lines.append("Unscheduled tasks:")
            for task in self.unscheduled_tasks:
                lines.append(f"- {task.title}")
        return "\n".join(lines)


class Scheduler:
    def __init__(
        self,
        owner: Owner,
        pet: Pet,
        tasks: List[CareTask],
        rules: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize the scheduler with owner context, pet, tasks, and rules."""
        self.owner = owner
        self.pet = pet
        self.tasks = tasks
        self.rules: Dict[str, Any] = rules or {}

    def generate_plan(self, date: DateType) -> DailyPlan:
        """Generate and return a daily plan from available tasks."""
        plan = DailyPlan(date=date)
        ranked_tasks = self.sort_or_rank_tasks()
        remaining = self.owner.get_daily_capacity()
        current_time = self.rules.get("day_start", "08:00")

        for task in ranked_tasks:
            if task.fits_in(remaining):
                end_time = self._add_minutes(current_time, task.duration_minutes)
                reason = "High-priority task that fits current time budget."
                plan.add_item(task, current_time, end_time, reason)
                remaining -= task.duration_minutes
                current_time = end_time
            else:
                plan.unscheduled_tasks.append(task)

        return plan

    def filter_feasible_tasks(self) -> List[CareTask]:
        """Return tasks that satisfy constraints (time, needs, preferences)."""
        all_tasks = self.owner.get_all_tasks()
        if not all_tasks:
            all_tasks = list(self.tasks)

        excluded_types = set(self.owner.preferences.get("exclude_task_types", []))
        feasible: List[CareTask] = []
        for task in all_tasks:
            if task.task_type in excluded_types:
                continue
            if task.due_window and not self.owner.is_available(task.due_window):
                continue
            feasible.append(task)
        return feasible

    def sort_or_rank_tasks(self) -> List[CareTask]:
        """Return tasks ordered by priority and scheduling heuristics."""
        feasible_tasks = self.filter_feasible_tasks()
        return sorted(
            feasible_tasks,
            key=lambda task: (
                0 if task.is_required else 1,
                -task.priority_score(),
                task.duration_minutes,
                task.title.lower(),
            ),
        )

    def build_explanations(self, plan: DailyPlan) -> Dict[str, str]:
        """Build explanation strings for scheduled/unscheduled decisions."""
        explanations: Dict[str, str] = {}
        for item in plan.scheduled_items:
            explanations[item.task.title] = item.reason
        for task in plan.unscheduled_tasks:
            explanations[task.title] = "Not scheduled due to limited remaining time."
        return explanations

    def _add_minutes(self, start_time: str, minutes: int) -> str:
        """Add minutes to HH:MM time strings."""
        hours, mins = start_time.split(":")
        total = int(hours) * 60 + int(mins) + minutes
        total %= 24 * 60
        end_hours = total // 60
        end_mins = total % 60
        return f"{end_hours:02d}:{end_mins:02d}"