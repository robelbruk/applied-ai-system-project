from __future__ import annotations

from unittest.mock import MagicMock

from ai.architect import CarePlanArchitect
from ai.evaluator import evaluate_all, evaluate_case


def _fake_llm_returning(json_body: str) -> MagicMock:
    llm = MagicMock()
    llm.complete.return_value = json_body
    return llm


def _case(**overrides):
    base = {
        "id": "t",
        "input": "Walk Buddy 20 min in the morning.",
        "owner": {"name": "Jordan", "minutes_per_day": 120},
        "pet": {"name": "Buddy", "species": "Dog", "age": 4},
        "expected_tasks": [
            {
                "match_keywords": ["walk"],
                "fields": {
                    "duration_minutes": 20,
                    "task_type": "exercise",
                    "due_window": "morning",
                    "pet_name": "Buddy",
                },
            }
        ],
    }
    base.update(overrides)
    return base


def test_evaluate_case_passes_on_exact_match() -> None:
    arch = CarePlanArchitect(
        llm=_fake_llm_returning(
            '{"tasks":[{"title":"Morning walk","duration_minutes":20,'
            '"priority":"high","task_type":"exercise","pet_name":"Buddy",'
            '"due_window":"morning","time":null,"is_required":false,'
            '"frequency":"daily"}]}'
        )
    )
    result = evaluate_case(_case(), arch)
    assert result.passed
    assert result.field_accuracy == 1.0


def test_evaluate_case_fails_on_wrong_duration() -> None:
    arch = CarePlanArchitect(
        llm=_fake_llm_returning(
            '{"tasks":[{"title":"Morning walk","duration_minutes":30,'
            '"priority":"high","task_type":"exercise","pet_name":"Buddy",'
            '"due_window":"morning","time":null,"is_required":false,'
            '"frequency":"daily"}]}'
        )
    )
    result = evaluate_case(_case(), arch)
    assert not result.passed
    assert 0 < result.field_accuracy < 1
    failed = [c for tr in result.task_results for c in tr.field_checks if not c.passed]
    assert any(c.key == "duration_minutes" for c in failed)


def test_evaluate_case_fails_when_no_matching_title() -> None:
    arch = CarePlanArchitect(
        llm=_fake_llm_returning(
            '{"tasks":[{"title":"Feed breakfast","duration_minutes":10,'
            '"priority":"urgent","task_type":"feeding","pet_name":"Buddy",'
            '"due_window":null,"time":"08:00","is_required":true,'
            '"frequency":"daily"}]}'
        )
    )
    result = evaluate_case(_case(), arch)
    assert not result.passed
    assert result.task_results[0].matched is False


def test_evaluate_all_filters_by_case_ids() -> None:
    arch = CarePlanArchitect(
        llm=_fake_llm_returning(
            '{"tasks":[{"title":"Walk","duration_minutes":20,"priority":"high",'
            '"task_type":"exercise","pet_name":"Buddy","due_window":"morning",'
            '"time":null,"is_required":false,"frequency":"daily"}]}'
        )
    )
    golden = {
        "cases": [
            _case(id="a"),
            _case(id="b"),
        ]
    }
    results = evaluate_all(architect=arch, case_ids=["b"], golden=golden)
    assert [r.case_id for r in results] == ["b"]
