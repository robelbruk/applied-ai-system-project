import os
from datetime import date

from pawpal_system import CareTask, DailyPlan, Owner, Pet, Scheduler


def build_demo_data() -> tuple[Owner, list[Pet], list[CareTask]]:
    """Create sample owner, pets, and tasks for a quick demo."""
    owner = Owner(
        name="Jordan",
        available_minutes_per_day=75,
        preferences={
            "availability": {"morning": True, "afternoon": True, "evening": True},
        },
    )

    dog = Pet(name="Buddy", species="Dog", age=5, special_needs=["exercise"])
    cat = Pet(name="Mochi", species="Cat", age=3, special_needs=["grooming"])

    # Define tasks first (reference order for return value — not chronological).
    evening_brush = CareTask(
        title="Evening Brush",
        duration_minutes=15,
        priority="medium",
        task_type="grooming",
        due_window="evening",
        frequency="daily",
    )
    afternoon_play = CareTask(
        title="Afternoon Play",
        duration_minutes=15,
        priority="high",
        task_type="exercise",
        due_window="afternoon",
        frequency="daily",
    )
    litter_check = CareTask(
        title="Litter Check",
        duration_minutes=10,
        priority="low",
        task_type="general",
        due_window="evening",
        frequency="daily",
    )
    walk = CareTask(
        title="Morning Walk",
        duration_minutes=25,
        priority="high",
        task_type="exercise",
        due_window="morning",
        frequency="daily",
        is_required=True,
    )
    breakfast = CareTask(
        title="Feed Breakfast",
        duration_minutes=10,
        priority="urgent",
        task_type="feeding",
        due_window="morning",
        frequency="daily",
        is_required=True,
    )

    # Add tasks in non-chronological order (evening → afternoon → evening → morning).
    cat.add_task(evening_brush)
    dog.add_task(afternoon_play)
    cat.add_task(litter_check)
    dog.add_task(walk)
    dog.add_task(breakfast)
    # Recurring daily: completes this instance and appends the next (due tomorrow).
    breakfast.mark_complete(pet=dog)

    owner.add_pet(dog)
    owner.add_pet(cat)

    tasks_in_creation_order = [
        evening_brush,
        afternoon_play,
        litter_check,
        walk,
        breakfast,
    ]
    return owner, [dog, cat], tasks_in_creation_order


def _print_task_lines(label: str, task_list: list[CareTask]) -> None:
    print(label)
    if not task_list:
        print("  (none)")
    else:
        for task in task_list:
            due = task.time or task.due_window or "anytime"
            due_date = f" due {task.due_date.isoformat()}" if task.due_date else ""
            status = "done" if task.is_completed else "pending"
            print(f"  - {task.title} | {task.pet_name} | {due}{due_date} | {status}")
    print()


def print_demo(owner: Owner, pets: list[Pet], tasks: list[CareTask]) -> None:
    """Print owner, pets, tasks, sorting, filtering, and generated schedule."""
    print("Owner")
    print(f"- Name: {owner.name}")
    print(f"- Daily Capacity: {owner.get_daily_capacity()} minutes")
    print()

    print("Pets")
    for pet in pets:
        print(f"- {pet.name} ({pet.species}, age {pet.age})")
    print()

    print("Tasks (definition / creation order — not sorted by time)")
    for task in tasks:
        due_time = task.due_window or "anytime"
        print(f"- {task.describe()} | Time: {due_time} | Frequency: {task.frequency}")
    print()

    storage_order = owner.get_all_tasks()
    _print_task_lines(
        "Tasks in storage order (owner.get_all_tasks — pet order, then add order)",
        storage_order,
    )

    scheduler = Scheduler(owner=owner, pet=pets[0], tasks=[])
    ranked = scheduler.sort_or_rank_tasks()
    _print_task_lines(
        "Sorted via Scheduler.sort_or_rank_tasks (time window, then required, priority, …)",
        ranked,
    )

    _print_task_lines(
        "Filter: incomplete tasks only (owner.filter_tasks is_completed=False)",
        owner.filter_tasks(is_completed=False),
    )
    _print_task_lines(
        "Filter: completed tasks only (owner.filter_tasks is_completed=True)",
        owner.filter_tasks(is_completed=True),
    )
    _print_task_lines(
        'Filter: Buddy only (owner.filter_tasks pet_name="Buddy")',
        owner.filter_tasks(pet_name="Buddy"),
    )
    _print_task_lines(
        'Filter: Mochi only (owner.filter_tasks pet_name="Mochi")',
        owner.filter_tasks(pet_name="Mochi"),
    )

    plan = scheduler.generate_plan(date.today())

    print("Today's Schedule")
    print(f"Date: {plan.date.isoformat()}")

    if not plan.scheduled_items:
        print("- No tasks scheduled.")
    else:
        for item in plan.scheduled_items:
            print(
                f"- {item.start_time} to {item.end_time}: "
                f"{item.task.title} for {item.task.pet_name} "
                f"({item.task.duration_minutes} min)"
            )

    if plan.unscheduled_tasks:
        print("Unscheduled Tasks")
        for task in plan.unscheduled_tasks:
            print(f"- {task.title}")

    print()
    print("Conflict detection (manual plan: two tasks overlap 14:10–14:20)")
    overlap_plan = DailyPlan(date=date.today())
    overlap_plan.add_item(
        CareTask(
            title="Vet callback",
            duration_minutes=20,
            priority="high",
            task_type="general",
            pet_name="Buddy",
        ),
        "14:00",
        "14:20",
        "demo overlap",
    )
    overlap_plan.add_item(
        CareTask(
            title="Grooming slot",
            duration_minutes=30,
            priority="medium",
            task_type="grooming",
            pet_name="Mochi",
        ),
        "14:10",
        "14:40",
        "demo overlap",
    )
    print(
        f"- 14:00–14:20: Vet callback (Buddy)  |  "
        f"14:10–14:40: Grooming slot (Mochi)  → same time window"
    )
    conflict_warning = scheduler.scheduling_conflict_warning(overlap_plan)
    assert conflict_warning is not None, "scheduler should warn when two tasks overlap"
    print(conflict_warning)
    print(f"(has_time_conflicts: {scheduler.has_time_conflicts(overlap_plan)})")


def demo_architect() -> None:
    """Run the Care Plan Architect on a canned NL prompt.

    Skipped gracefully if HF_TOKEN is not set so the rest of the demo still
    works in environments without the API key.
    """
    if not os.environ.get("HF_TOKEN"):
        print("Care Plan Architect demo skipped (HF_TOKEN not set).")
        print("Set HF_TOKEN to run: https://huggingface.co/settings/tokens")
        print()
        return

    from ai.architect import CarePlanArchitect

    prompt = (
        "My dog Buddy needs a 25-min morning walk and breakfast at 8am (required). "
        "Mochi the cat should get a 15-min evening brushing."
    )
    owner = Owner(name="Jordan", available_minutes_per_day=120)
    pet = Pet(name="Buddy", species="Dog", age=4)
    owner.add_pet(pet)

    print("Care Plan Architect demo")
    print(f"Input: {prompt}")
    print()

    architect = CarePlanArchitect()
    trace = architect.run(prompt, owner, pet)

    if trace.error:
        print(f"Architect failed: {trace.error}")
        for err in trace.validation_errors:
            print(f"  - {err}")
        return

    print(f"Extracted {len(trace.drafts)} task(s) (retries: {trace.retry_count}):")
    for draft in trace.drafts:
        when = draft.time or draft.due_window or "anytime"
        print(
            f"  - {draft.title} [{draft.priority}/{draft.task_type}] "
            f"{draft.duration_minutes} min @ {when}"
            f"{' (required)' if draft.is_required else ''}"
        )
    print()

    if trace.plan:
        print(f"Schedule for {trace.plan.date.isoformat()}")
        for item in trace.plan.scheduled_items:
            print(
                f"  - {item.start_time}-{item.end_time}: {item.task.title} "
                f"for {item.task.pet_name}"
            )
        if trace.conflict_warning:
            print(trace.conflict_warning)
        else:
            print("No scheduling conflicts detected.")
    print()


if __name__ == "__main__":
    demo_owner, demo_pets, demo_tasks = build_demo_data()
    print_demo(demo_owner, demo_pets, demo_tasks)
    demo_architect()
