from datetime import date

from pawpal_system import CareTask, Owner, Pet, Scheduler


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

    # Using CareTask from pawpal_system as the project's task class.
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
    brush = CareTask(
        title="Evening Brush",
        duration_minutes=15,
        priority="medium",
        task_type="grooming",
        due_window="evening",
        frequency="daily",
    )

    dog.add_task(walk)
    dog.add_task(breakfast)
    cat.add_task(brush)

    owner.add_pet(dog)
    owner.add_pet(cat)

    return owner, [dog, cat], [walk, breakfast, brush]


def print_demo(owner: Owner, pets: list[Pet], tasks: list[CareTask]) -> None:
    """Print owner, pets, tasks, and generated schedule."""
    print("Owner")
    print(f"- Name: {owner.name}")
    print(f"- Daily Capacity: {owner.get_daily_capacity()} minutes")
    print()

    print("Pets")
    for pet in pets:
        print(f"- {pet.name} ({pet.species}, age {pet.age})")
    print()

    print("Tasks")
    for task in tasks:
        due_time = task.due_window or "anytime"
        print(f"- {task.describe()} | Time: {due_time} | Frequency: {task.frequency}")
    print()

    scheduler = Scheduler(owner=owner, pet=pets[0], tasks=[])
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


if __name__ == "__main__":
    demo_owner, demo_pets, demo_tasks = build_demo_data()
    print_demo(demo_owner, demo_pets, demo_tasks)
