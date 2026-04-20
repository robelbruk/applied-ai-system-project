from __future__ import annotations

import re
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from pawpal_system import CareTask

_HHMM = re.compile(r"^\d{1,2}:\d{2}$")

Priority = Literal["low", "medium", "high", "urgent"]
TaskType = Literal["exercise", "feeding", "grooming", "medical", "training", "general"]
Frequency = Literal["once", "daily", "weekly"]
DueWindow = Literal["morning", "afternoon", "evening", "night"]


class TaskDraft(BaseModel):
    """Strict intermediate form between LLM output and :class:`CareTask`.

    Enforces enum membership, duration bounds (1–240 min), and ``HH:MM`` time
    format so invalid drafts never reach the Scheduler.
    """

    title: str = Field(min_length=1, max_length=80)
    duration_minutes: int = Field(ge=1, le=240)
    priority: Priority
    task_type: TaskType
    pet_name: Optional[str] = None
    due_window: Optional[DueWindow] = None
    time: Optional[str] = None
    is_required: bool = False
    frequency: Frequency = "daily"

    @field_validator("time")
    @classmethod
    def _validate_time(cls, value: Optional[str]) -> Optional[str]:
        if value is None or value == "":
            return None
        if not _HHMM.match(value):
            raise ValueError(f"time must be HH:MM, got {value!r}")
        hh, mm = value.split(":")
        h, m = int(hh), int(mm)
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError(f"time out of range: {value!r}")
        return f"{h:02d}:{m:02d}"

    def to_care_task(self) -> CareTask:
        return CareTask(
            title=self.title,
            duration_minutes=self.duration_minutes,
            priority=self.priority,
            task_type=self.task_type,
            pet_name=self.pet_name,
            due_window=self.due_window,
            time=self.time,
            is_required=self.is_required,
            frequency=self.frequency,
        )


class TaskDraftList(BaseModel):
    tasks: List[TaskDraft]
