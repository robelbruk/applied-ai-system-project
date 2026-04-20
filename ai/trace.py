from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from pawpal_system import CareTask, DailyPlan

from ai.critic import CriticReport
from ai.validators import TaskDraft


@dataclass
class ArchitectTrace:
    """Observable record of every stage the architect went through.

    Populated incrementally so the UI / CLI can show what happened even if a
    later stage fails.
    """

    user_text: str
    raw_llm_output: str = ""
    drafts: List[TaskDraft] = field(default_factory=list)
    validation_errors: List[str] = field(default_factory=list)
    care_tasks: List[CareTask] = field(default_factory=list)
    plan: Optional[DailyPlan] = None
    conflict_warning: Optional[str] = None
    retry_count: int = 0
    error: Optional[str] = None
    critic: Optional[CriticReport] = None

    def succeeded(self) -> bool:
        return self.error is None and self.plan is not None
