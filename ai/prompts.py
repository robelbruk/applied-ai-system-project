from __future__ import annotations

SYSTEM_INSTRUCTIONS = """You are the PawPal+ Care Plan Architect.
You convert an owner's natural-language description of their day into a
strictly-validated JSON list of pet-care tasks.

You MUST:
1. Respond with a single JSON object of the form {"tasks": [...]} and nothing else.
   No markdown, no code fence, no commentary.
2. Each task object uses ONLY these fields:
   - title: short string (<= 80 chars)
   - duration_minutes: integer between 1 and 240
   - priority: one of "low" | "medium" | "high" | "urgent"
   - task_type: one of "exercise" | "feeding" | "grooming" | "medical" | "training" | "general"
   - pet_name: string or null
   - due_window: "morning" | "afternoon" | "evening" | "night" or null
   - time: 24-hour "HH:MM" string or null
   - is_required: boolean
   - frequency: "once" | "daily" | "weekly"
3. Defaults:
   - Meals -> task_type "feeding", priority "urgent", is_required true.
   - Walks/play -> task_type "exercise", priority "high".
   - Vet / meds -> task_type "medical", priority "urgent", is_required true.
   - Brushing / bath -> task_type "grooming", priority "medium".
4. If the owner gives a clock time ("8am", "2:30pm"), convert to 24h "HH:MM"
   and set `time`, leave `due_window` null.
5. If only a vague time ("morning", "evening"), set `due_window`, leave `time` null.
6. Do NOT invent tasks the owner did not mention.
7. If a detail is unknown, use null — never guess a pet name that was not given.
"""


_EXAMPLE_INPUT = (
    "Buddy the dog needs a 25-min walk in the morning and breakfast at 8am (required). "
    "Mochi the cat should get a 15-min evening brushing."
)

_EXAMPLE_OUTPUT = (
    '{"tasks":['
    '{"title":"Morning walk","duration_minutes":25,"priority":"high",'
    '"task_type":"exercise","pet_name":"Buddy","due_window":"morning","time":null,'
    '"is_required":false,"frequency":"daily"},'
    '{"title":"Breakfast","duration_minutes":10,"priority":"urgent",'
    '"task_type":"feeding","pet_name":"Buddy","due_window":null,"time":"08:00",'
    '"is_required":true,"frequency":"daily"},'
    '{"title":"Evening brushing","duration_minutes":15,"priority":"medium",'
    '"task_type":"grooming","pet_name":"Mochi","due_window":"evening","time":null,'
    '"is_required":false,"frequency":"daily"}'
    "]}"
)


def build_messages(user_text: str) -> list[dict]:
    """Return messages for an HF chat-completion call.

    Gemma lacks a native system role, so instructions are prepended to the
    first user turn. A single few-shot example anchors the JSON schema.
    """
    primer = (
        f"{SYSTEM_INSTRUCTIONS}\n\n"
        f"Example input:\n{_EXAMPLE_INPUT}"
    )
    return [
        {"role": "user", "content": primer},
        {"role": "assistant", "content": _EXAMPLE_OUTPUT},
        {"role": "user", "content": user_text},
    ]


def build_repair_messages(
    user_text: str, bad_output: str, error: str
) -> list[dict]:
    """Messages for a single repair retry after a parse/validation failure."""
    base = build_messages(user_text)
    base.append({"role": "assistant", "content": bad_output})
    base.append(
        {
            "role": "user",
            "content": (
                f"That response was invalid: {error}\n"
                "Return ONLY the JSON object with a `tasks` array using the schema above. "
                "No markdown, no explanation."
            ),
        }
    )
    return base
