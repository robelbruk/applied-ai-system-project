import pytest
from pydantic import ValidationError

from ai.validators import TaskDraft, TaskDraftList


def test_task_draft_accepts_minimal_valid_input() -> None:
    draft = TaskDraft(
        title="Walk", duration_minutes=20, priority="high", task_type="exercise"
    )
    assert draft.frequency == "daily"
    assert draft.is_required is False
    task = draft.to_care_task()
    assert task.title == "Walk"
    assert task.duration_minutes == 20


def test_task_draft_rejects_invalid_priority_enum() -> None:
    with pytest.raises(ValidationError):
        TaskDraft(
            title="X",
            duration_minutes=10,
            priority="super-urgent",
            task_type="general",
        )


def test_task_draft_rejects_invalid_task_type_enum() -> None:
    with pytest.raises(ValidationError):
        TaskDraft(
            title="X", duration_minutes=10, priority="low", task_type="vibes"
        )


def test_task_draft_rejects_duration_over_bound() -> None:
    with pytest.raises(ValidationError):
        TaskDraft(
            title="X", duration_minutes=9999, priority="low", task_type="general"
        )


def test_task_draft_rejects_duration_under_bound() -> None:
    with pytest.raises(ValidationError):
        TaskDraft(
            title="X", duration_minutes=0, priority="low", task_type="general"
        )


def test_task_draft_rejects_malformed_time() -> None:
    with pytest.raises(ValidationError):
        TaskDraft(
            title="X",
            duration_minutes=10,
            priority="low",
            task_type="general",
            time="99:99",
        )


def test_task_draft_normalizes_time_padding() -> None:
    draft = TaskDraft(
        title="X",
        duration_minutes=10,
        priority="low",
        task_type="general",
        time="8:05",
    )
    assert draft.time == "08:05"


def test_task_draft_list_rejects_missing_field() -> None:
    with pytest.raises(ValidationError):
        TaskDraftList.model_validate(
            {"tasks": [{"title": "X", "duration_minutes": 10, "priority": "low"}]}
        )
