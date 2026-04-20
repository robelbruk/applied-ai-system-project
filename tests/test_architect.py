from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from pawpal_system import Owner, Pet

from ai.architect import CarePlanArchitect, _parse_and_validate, _strip_code_fence


def _valid_json_single_task() -> str:
    return (
        '{"tasks":[{"title":"Walk","duration_minutes":20,"priority":"high",'
        '"task_type":"exercise","pet_name":"Buddy","due_window":"morning",'
        '"time":null,"is_required":true,"frequency":"daily"}]}'
    )


def test_parse_and_validate_accepts_clean_json() -> None:
    drafts = _parse_and_validate(_valid_json_single_task())
    assert len(drafts) == 1
    assert drafts[0].title == "Walk"
    assert drafts[0].task_type == "exercise"


def test_parse_and_validate_strips_markdown_fence() -> None:
    raw = "```json\n" + _valid_json_single_task() + "\n```"
    drafts = _parse_and_validate(raw)
    assert drafts[0].title == "Walk"


def test_parse_and_validate_extracts_json_from_prose() -> None:
    raw = "Sure, here you go:\n" + _valid_json_single_task() + "\nHope that helps!"
    drafts = _parse_and_validate(raw)
    assert drafts[0].title == "Walk"


def test_parse_and_validate_accepts_bare_list() -> None:
    raw = (
        '[{"title":"Feed","duration_minutes":5,"priority":"urgent",'
        '"task_type":"feeding"}]'
    )
    drafts = _parse_and_validate(raw)
    assert drafts[0].task_type == "feeding"


def test_parse_and_validate_rejects_invalid_duration() -> None:
    raw = (
        '{"tasks":[{"title":"X","duration_minutes":9999,"priority":"low",'
        '"task_type":"general"}]}'
    )
    with pytest.raises(Exception):
        _parse_and_validate(raw)


def test_strip_code_fence_handles_plain_text() -> None:
    assert _strip_code_fence('{"tasks":[]}') == '{"tasks":[]}'


def test_architect_run_produces_plan_with_mock_llm() -> None:
    mock_llm = MagicMock()
    mock_llm.complete.return_value = _valid_json_single_task()
    architect = CarePlanArchitect(llm=mock_llm)

    owner = Owner(name="Jordan", available_minutes_per_day=120)
    pet = Pet(name="Buddy", species="Dog", age=4)
    owner.add_pet(pet)

    trace = architect.run(
        "Walk Buddy 20 min in the morning.", owner, pet, date=date(2025, 6, 1)
    )
    assert trace.error is None
    assert trace.succeeded()
    assert len(trace.care_tasks) == 1
    assert trace.care_tasks[0].pet_name == "Buddy"
    assert trace.plan is not None
    assert len(trace.plan.scheduled_items) == 1


def test_architect_retries_once_after_invalid_first_response() -> None:
    mock_llm = MagicMock()
    mock_llm.complete.side_effect = [
        "absolutely not valid json",
        _valid_json_single_task(),
    ]
    architect = CarePlanArchitect(llm=mock_llm, max_retries=1)

    owner = Owner(name="Jordan", available_minutes_per_day=60)
    pet = Pet(name="Buddy", species="Dog", age=1)
    owner.add_pet(pet)

    trace = architect.run("Walk Buddy.", owner, pet, date=date(2025, 6, 1))
    assert trace.error is None
    assert trace.retry_count == 1
    assert len(trace.drafts) == 1
    assert mock_llm.complete.call_count == 2


def test_architect_records_error_when_both_attempts_fail() -> None:
    mock_llm = MagicMock()
    mock_llm.complete.return_value = "still not json"
    architect = CarePlanArchitect(llm=mock_llm, max_retries=1)

    owner = Owner(name="Jordan", available_minutes_per_day=60)
    pet = Pet(name="Buddy", species="Dog", age=1)
    owner.add_pet(pet)

    trace = architect.run("???", owner, pet, date=date(2025, 6, 1))
    assert trace.error is not None
    assert trace.plan is None
    assert trace.retry_count == 2
    assert len(trace.validation_errors) == 2


def test_architect_rejects_llm_output_with_invalid_enum() -> None:
    """Pydantic validator blocks tasks before they reach the Scheduler."""
    mock_llm = MagicMock()
    # Same shape on both attempts so repair also fails
    mock_llm.complete.return_value = (
        '{"tasks":[{"title":"X","duration_minutes":10,'
        '"priority":"super-urgent","task_type":"general"}]}'
    )
    architect = CarePlanArchitect(llm=mock_llm, max_retries=1)

    owner = Owner(name="Jordan", available_minutes_per_day=60)
    pet = Pet(name="Buddy", species="Dog", age=1)
    trace = architect.run("bad", owner, pet, date=date(2025, 6, 1))
    assert trace.error is not None
    assert any("priority" in err for err in trace.validation_errors)
