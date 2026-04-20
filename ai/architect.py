from __future__ import annotations

import json
import logging
import re
from datetime import date as DateType
from typing import List, Optional

from pydantic import ValidationError

from pawpal_system import CareTask, Owner, Pet, Scheduler

from ai.client import ArchitectLLM
from ai.critic import review as critic_review
from ai.prompts import build_messages, build_repair_messages
from ai.trace import ArchitectTrace
from ai.validators import TaskDraft, TaskDraftList

logger = logging.getLogger("pawpal.ai.architect")

_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


class CarePlanArchitect:
    """Converts natural-language care requests into a scheduled DailyPlan.

    Pipeline: NL text -> LLM JSON -> Pydantic TaskDraft -> CareTask ->
    Pet.add_task -> Scheduler.generate_plan -> conflict check. Every stage
    is recorded on :class:`ArchitectTrace` for observable output.
    """

    def __init__(
        self,
        llm: Optional[ArchitectLLM] = None,
        max_retries: int = 1,
    ) -> None:
        self.llm = llm if llm is not None else ArchitectLLM()
        self.max_retries = max_retries

    def parse(self, text: str, trace: ArchitectTrace) -> List[TaskDraft]:
        """Call the LLM and return validated drafts; one repair retry on failure."""
        messages = build_messages(text)
        last_error: Optional[str] = None
        last_raw: str = ""
        for attempt in range(self.max_retries + 1):
            raw = self.llm.complete(messages)
            last_raw = raw
            trace.raw_llm_output = raw
            try:
                drafts = _parse_and_validate(raw)
                trace.drafts = drafts
                return drafts
            except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                last_error = _format_error(exc)
                trace.validation_errors.append(
                    f"attempt {attempt + 1}: {last_error}"
                )
                trace.retry_count = attempt + 1
                logger.warning(
                    "architect parse failed (attempt %d): %s", attempt + 1, last_error
                )
                if attempt < self.max_retries:
                    messages = build_repair_messages(text, last_raw, last_error)
                    continue
        raise ValueError(
            f"Architect failed after {self.max_retries + 1} attempt(s): {last_error}"
        )

    def run(
        self,
        text: str,
        owner: Owner,
        pet: Pet,
        date: Optional[DateType] = None,
    ) -> ArchitectTrace:
        """End-to-end: parse, attach tasks to pet, schedule, check conflicts."""
        trace = ArchitectTrace(user_text=text)
        known_pet_names = [p.name for p in owner.get_pets()] or [pet.name]

        try:
            drafts = self.parse(text, trace)
        except ValueError as exc:
            trace.error = str(exc)
            trace.critic = critic_review(
                user_text=text,
                drafts=[],
                plan=None,
                conflict_warning=None,
                known_pet_names=known_pet_names,
            )
            return trace

        care_tasks: List[CareTask] = []
        for draft in drafts:
            task = draft.to_care_task()
            if task.pet_name is None:
                task.pet_name = pet.name
            pet.add_task(task)
            care_tasks.append(task)
        trace.care_tasks = care_tasks

        scheduler = Scheduler(owner=owner, pet=pet, tasks=pet.get_tasks())
        plan = scheduler.generate_plan(date or DateType.today())
        trace.plan = plan
        trace.conflict_warning = scheduler.scheduling_conflict_warning(plan)
        trace.critic = critic_review(
            user_text=text,
            drafts=drafts,
            plan=plan,
            conflict_warning=trace.conflict_warning,
            known_pet_names=known_pet_names,
        )
        return trace


def _parse_and_validate(raw: str) -> List[TaskDraft]:
    """Parse the LLM text to ``TaskDraftList.tasks``.

    Tolerates markdown code fences and leading/trailing prose by extracting
    the first JSON object substring. Accepts a bare list (wraps as ``{tasks}``)
    or the standard ``{"tasks": [...]}`` envelope.
    """
    cleaned = _strip_code_fence(raw).strip()
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        match = _JSON_OBJECT.search(cleaned)
        if not match:
            raise
        payload = json.loads(match.group(0))
    if isinstance(payload, list):
        payload = {"tasks": payload}
    validated = TaskDraftList.model_validate(payload)
    return validated.tasks


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines)


def _format_error(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        issues = [
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}"
            for err in exc.errors()
        ]
        return "; ".join(issues) or str(exc)
    return str(exc)
