"""Self-critique + confidence scoring for architect output.

Deterministic heuristic review — no second LLM call — so the critic is:
- cheap (runs offline),
- testable (same input -> same report),
- auditable (each deduction traces to a named check).

If the user text signals something (a pet name, a time) that didn't make it
into any draft, that's an ``info`` issue. If the plan has unscheduled tasks
or overlapping intervals, that's a ``warning``. Empty drafts are an
``error``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, List, Literal, Optional, Sequence

from pawpal_system import DailyPlan

from ai.validators import TaskDraft

Severity = Literal["info", "warning", "error"]

_CLOCK_TIME = re.compile(r"\b\d{1,2}\s*(?::\d{2})?\s*(?:am|pm)\b", re.IGNORECASE)
_DAY_PART = re.compile(r"\b(morning|afternoon|evening|night)\b", re.IGNORECASE)

_SEVERITY_DEDUCTION = {"error": 0.35, "warning": 0.15, "info": 0.05}
_MIN_USEFUL_TEXT_LEN = 15


@dataclass(frozen=True)
class Issue:
    severity: Severity
    category: str
    message: str


@dataclass
class CriticReport:
    confidence: float
    issues: List[Issue] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(i.severity == "warning" for i in self.issues)

    def summary(self) -> str:
        if not self.issues:
            return f"Confidence {self.confidence:.2f}. No issues detected."
        head = f"Confidence {self.confidence:.2f} ({len(self.issues)} issue(s))."
        lines = [head] + [f"- [{i.severity}] {i.category}: {i.message}" for i in self.issues]
        return "\n".join(lines)


def review(
    *,
    user_text: str,
    drafts: Sequence[TaskDraft],
    plan: Optional[DailyPlan],
    conflict_warning: Optional[str],
    known_pet_names: Iterable[str] = (),
) -> CriticReport:
    """Score the architect's output against a handful of sanity checks.

    Args:
        user_text: The original natural-language request.
        drafts: Validated ``TaskDraft`` list the architect produced.
        plan: ``DailyPlan`` from ``Scheduler.generate_plan`` (None on failure).
        conflict_warning: Output of ``Scheduler.scheduling_conflict_warning``.
        known_pet_names: Names the architect was allowed to assign to (e.g.,
            the pets on the owner). Used to detect pets mentioned in text but
            not referenced by any draft.
    """
    issues: List[Issue] = []

    if not drafts:
        issues.append(
            Issue(
                severity="error",
                category="extraction",
                message="No tasks were extracted from the input.",
            )
        )
        return CriticReport(confidence=0.0, issues=issues)

    if len(user_text.strip()) < _MIN_USEFUL_TEXT_LEN:
        issues.append(
            Issue(
                severity="warning",
                category="input",
                message=(
                    f"Input is very short ({len(user_text.strip())} chars); "
                    "consider adding duration, priority, and time."
                ),
            )
        )

    # Time-hint coverage: does the user reference times that no draft captured?
    text_has_clock = bool(_CLOCK_TIME.search(user_text))
    text_has_daypart = bool(_DAY_PART.search(user_text))
    drafts_have_clock = any(d.time for d in drafts)
    drafts_have_window = any(d.due_window for d in drafts)
    if text_has_clock and not drafts_have_clock:
        issues.append(
            Issue(
                severity="info",
                category="extraction",
                message="Input mentions a clock time but no draft captured a `time` field.",
            )
        )
    if text_has_daypart and not drafts_have_window and not drafts_have_clock:
        issues.append(
            Issue(
                severity="info",
                category="extraction",
                message="Input mentions a day part (morning/evening/etc.) but no draft captured it.",
            )
        )

    # Pet-name coverage: pet mentioned by name in text but no draft used it.
    text_lower = user_text.lower()
    draft_pets = {(d.pet_name or "").lower() for d in drafts}
    for name in known_pet_names:
        if name and name.lower() in text_lower and name.lower() not in draft_pets:
            issues.append(
                Issue(
                    severity="info",
                    category="extraction",
                    message=f"Pet '{name}' appears in the input but no draft assigns tasks to them.",
                )
            )

    # Draft plausibility
    for d in drafts:
        if d.duration_minutes >= 120:
            issues.append(
                Issue(
                    severity="info",
                    category="draft",
                    message=f"'{d.title}' is unusually long ({d.duration_minutes} min); verify.",
                )
            )
        if d.task_type == "general" and d.priority in ("high", "urgent"):
            issues.append(
                Issue(
                    severity="info",
                    category="draft",
                    message=f"'{d.title}' is high-priority but task_type is 'general'; consider a specific type.",
                )
            )

    # Plan health
    if plan is not None:
        if plan.unscheduled_tasks:
            issues.append(
                Issue(
                    severity="warning",
                    category="plan",
                    message=(
                        f"{len(plan.unscheduled_tasks)} task(s) did not fit in the owner's "
                        "daily capacity."
                    ),
                )
            )
        if conflict_warning:
            issues.append(
                Issue(
                    severity="warning",
                    category="plan",
                    message="Plan has overlapping intervals; see scheduler conflict warning.",
                )
            )

    confidence = _score(issues)
    return CriticReport(confidence=confidence, issues=issues)


def _score(issues: Sequence[Issue]) -> float:
    score = 1.0
    for issue in issues:
        score -= _SEVERITY_DEDUCTION.get(issue.severity, 0.0)
    return max(0.0, min(1.0, round(score, 3)))
