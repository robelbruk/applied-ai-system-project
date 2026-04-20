from __future__ import annotations

from datetime import date

from pawpal_system import CareTask, DailyPlan

from ai.critic import Issue, review
from ai.validators import TaskDraft


def _draft(**overrides) -> TaskDraft:
    base = dict(
        title="Walk",
        duration_minutes=20,
        priority="high",
        task_type="exercise",
        pet_name="Buddy",
    )
    base.update(overrides)
    return TaskDraft(**base)


def test_empty_drafts_give_zero_confidence_and_error() -> None:
    report = review(
        user_text="take care of pets",
        drafts=[],
        plan=None,
        conflict_warning=None,
    )
    assert report.confidence == 0.0
    assert report.has_errors
    assert any(i.category == "extraction" for i in report.issues)


def test_clean_drafts_and_plan_give_high_confidence() -> None:
    draft = _draft(time="08:00", is_required=True)
    plan = DailyPlan(date=date(2025, 6, 1))
    plan.add_item(draft.to_care_task(), "08:00", "08:20", "")
    report = review(
        user_text="Walk Buddy 20 min at 8am.",
        drafts=[draft],
        plan=plan,
        conflict_warning=None,
        known_pet_names=["Buddy"],
    )
    assert report.confidence >= 0.9
    assert not report.has_errors
    assert not report.has_warnings


def test_unscheduled_tasks_lower_confidence_to_warning_band() -> None:
    draft = _draft()
    plan = DailyPlan(date=date(2025, 6, 1))
    plan.unscheduled_tasks.append(draft.to_care_task())
    report = review(
        user_text="Walk Buddy 20 min in the morning.",
        drafts=[draft],
        plan=plan,
        conflict_warning=None,
        known_pet_names=["Buddy"],
    )
    assert report.has_warnings
    assert report.confidence < 1.0


def test_conflict_warning_produces_warning_issue() -> None:
    draft = _draft()
    plan = DailyPlan(date=date(2025, 6, 1))
    report = review(
        user_text="Walk Buddy 20 min.",
        drafts=[draft],
        plan=plan,
        conflict_warning="Warning: 1 overlapping slot.",
        known_pet_names=["Buddy"],
    )
    assert any(i.severity == "warning" and i.category == "plan" for i in report.issues)


def test_unmentioned_pet_in_text_flags_info_issue() -> None:
    # Drafts assign to Buddy but text also names Mochi
    draft = _draft()
    plan = DailyPlan(date=date(2025, 6, 1))
    report = review(
        user_text="Walk Buddy 20 min and brush Mochi later.",
        drafts=[draft],
        plan=plan,
        conflict_warning=None,
        known_pet_names=["Buddy", "Mochi"],
    )
    assert any(
        i.severity == "info" and "Mochi" in i.message for i in report.issues
    )


def test_clock_time_in_text_but_not_extracted_is_flagged() -> None:
    draft = _draft()  # no `time` field
    plan = DailyPlan(date=date(2025, 6, 1))
    report = review(
        user_text="Walk Buddy 20 minutes at 8am please.",
        drafts=[draft],
        plan=plan,
        conflict_warning=None,
        known_pet_names=["Buddy"],
    )
    assert any("clock time" in i.message for i in report.issues)


def test_short_input_produces_warning() -> None:
    draft = _draft()
    report = review(
        user_text="walk",
        drafts=[draft],
        plan=None,
        conflict_warning=None,
    )
    assert any(i.severity == "warning" and i.category == "input" for i in report.issues)


def test_issue_dataclass_is_hashable_and_frozen() -> None:
    # Defensive: frozen dataclass so reports can be diffed/set-compared.
    i = Issue(severity="info", category="extraction", message="x")
    {i}  # should not raise
