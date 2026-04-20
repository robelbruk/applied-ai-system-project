"""Golden-set evaluator for the Care Plan Architect.

Reads ``ai/golden_set.json``, runs each NL case through the architect, and
scores extracted drafts against field-level expectations.

Run:

    python -m ai.evaluator                  # all cases, real LLM (needs HF_TOKEN)
    python -m ai.evaluator --case simple_walk  # one case
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from pawpal_system import Owner, Pet

from ai.architect import CarePlanArchitect
from ai.trace import ArchitectTrace
from ai.validators import TaskDraft

logger = logging.getLogger("pawpal.ai.evaluator")

GOLDEN_PATH = Path(__file__).resolve().parent / "golden_set.json"


@dataclass
class FieldCheck:
    key: str
    expected: Any
    actual: Any
    passed: bool


@dataclass
class TaskCaseResult:
    match_keywords: List[str]
    matched_title: Optional[str]
    field_checks: List[FieldCheck] = field(default_factory=list)

    @property
    def matched(self) -> bool:
        return self.matched_title is not None

    @property
    def field_pass_rate(self) -> float:
        if not self.field_checks:
            return 1.0 if self.matched else 0.0
        passed = sum(1 for c in self.field_checks if c.passed)
        return passed / len(self.field_checks)

    @property
    def all_passed(self) -> bool:
        return self.matched and all(c.passed for c in self.field_checks)


@dataclass
class CaseResult:
    case_id: str
    input_text: str
    trace: ArchitectTrace
    task_results: List[TaskCaseResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        if self.trace.error:
            return False
        return all(tr.all_passed for tr in self.task_results)

    @property
    def field_accuracy(self) -> float:
        total = sum(len(tr.field_checks) for tr in self.task_results)
        if total == 0:
            return 1.0 if self.passed else 0.0
        passed = sum(
            sum(1 for c in tr.field_checks if c.passed) for tr in self.task_results
        )
        return passed / total


def _load_golden(path: Path = GOLDEN_PATH) -> Dict[str, Any]:
    with path.open() as f:
        return json.load(f)


def _build_owner_pet(case: Dict[str, Any]) -> tuple[Owner, Pet]:
    owner_spec = case.get("owner", {})
    pet_spec = case.get("pet", {})
    owner = Owner(
        name=owner_spec.get("name", "Evaluator"),
        available_minutes_per_day=int(owner_spec.get("minutes_per_day", 120)),
    )
    pet = Pet(
        name=pet_spec.get("name", "Buddy"),
        species=pet_spec.get("species", "Dog"),
        age=int(pet_spec.get("age", 3)),
    )
    owner.add_pet(pet)
    return owner, pet


def _find_matching_draft(
    drafts: Sequence[TaskDraft], keywords: Sequence[str]
) -> Optional[TaskDraft]:
    needles = [k.lower() for k in keywords]
    for d in drafts:
        title = d.title.lower()
        if all(n in title for n in needles):
            return d
    return None


def _check_field(expected: Any, actual: Any) -> bool:
    if isinstance(expected, str) and isinstance(actual, str):
        return expected.strip().lower() == actual.strip().lower()
    return expected == actual


def evaluate_case(
    case: Dict[str, Any], architect: CarePlanArchitect
) -> CaseResult:
    owner, pet = _build_owner_pet(case)
    trace = architect.run(case["input"], owner, pet)

    result = CaseResult(case_id=case["id"], input_text=case["input"], trace=trace)

    for expected_task in case.get("expected_tasks", []):
        keywords = expected_task.get("match_keywords", [])
        match = _find_matching_draft(trace.drafts, keywords)
        task_result = TaskCaseResult(
            match_keywords=keywords,
            matched_title=match.title if match else None,
        )
        if match is not None:
            for key, expected_val in expected_task.get("fields", {}).items():
                actual_val = getattr(match, key, None)
                task_result.field_checks.append(
                    FieldCheck(
                        key=key,
                        expected=expected_val,
                        actual=actual_val,
                        passed=_check_field(expected_val, actual_val),
                    )
                )
        result.task_results.append(task_result)
    return result


def evaluate_all(
    architect: Optional[CarePlanArchitect] = None,
    case_ids: Optional[Sequence[str]] = None,
    golden: Optional[Dict[str, Any]] = None,
) -> List[CaseResult]:
    arch = architect if architect is not None else CarePlanArchitect()
    data = golden if golden is not None else _load_golden()
    cases = data.get("cases", [])
    if case_ids:
        wanted = set(case_ids)
        cases = [c for c in cases if c["id"] in wanted]
    return [evaluate_case(c, arch) for c in cases]


def print_report(results: Sequence[CaseResult]) -> None:
    if not results:
        print("No cases evaluated.")
        return

    passed = sum(1 for r in results if r.passed)
    total_checks = sum(len(tr.field_checks) for r in results for tr in r.task_results)
    passed_checks = sum(
        1
        for r in results
        for tr in r.task_results
        for c in tr.field_checks
        if c.passed
    )
    confidences = [r.trace.critic.confidence for r in results if r.trace.critic]

    print("=" * 68)
    print("Care Plan Architect — golden-set evaluation")
    print("=" * 68)
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        conf = (
            f"conf={r.trace.critic.confidence:.2f}"
            if r.trace.critic
            else "conf=n/a"
        )
        print(f"[{status}] {r.case_id}  ({conf}, field_acc={r.field_accuracy:.0%})")
        if r.trace.error:
            print(f"    ERROR: {r.trace.error}")
        for tr in r.task_results:
            if not tr.matched:
                print(f"    - missing task matching {tr.match_keywords}")
                continue
            for c in tr.field_checks:
                if not c.passed:
                    print(
                        f"    - {tr.matched_title}.{c.key}: "
                        f"expected {c.expected!r}, got {c.actual!r}"
                    )
    print("-" * 68)
    print(f"Cases passed:  {passed}/{len(results)}")
    if total_checks:
        print(f"Field checks:  {passed_checks}/{total_checks} ({passed_checks / total_checks:.0%})")
    if confidences:
        avg = sum(confidences) / len(confidences)
        print(f"Avg critic confidence: {avg:.2f}")
    print("=" * 68)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case", action="append", help="Run only these case ids (may be repeated)"
    )
    parser.add_argument(
        "--golden",
        type=Path,
        default=GOLDEN_PATH,
        help="Path to a golden-set JSON file (default: ai/golden_set.json)",
    )
    args = parser.parse_args(argv)

    try:
        results = evaluate_all(
            case_ids=args.case,
            golden=_load_golden(args.golden),
        )
    except RuntimeError as exc:
        print(f"Evaluator could not run: {exc}", file=sys.stderr)
        return 2

    print_report(results)
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
