from datetime import date, timedelta

from pawpal_system import CareTask, DailyPlan, Owner, Pet, Scheduler, filter_care_tasks


def test_task_mark_complete_updates_completion_status() -> None:
    task = CareTask(
        title="Feed Dinner",
        duration_minutes=15,
        priority="high",
        task_type="feeding",
        due_window="evening",
    )

    assert task.is_completed is False
    task.mark_complete()
    assert task.is_completed is True


def test_sort_or_rank_tasks_chronological_order() -> None:
    """Feasible tasks are ordered by time-of-day (earlier clock times first)."""
    owner = Owner(name="Alex", available_minutes_per_day=240)
    dog = Pet(name="Buddy", species="Dog", age=3)
    owner.add_pet(dog)
    # Same duration, priority, and optional flag so ordering is driven by `time`.
    dog.add_task(
        CareTask(
            title="Afternoon",
            duration_minutes=10,
            priority="medium",
            task_type="general",
            time="14:00",
        )
    )
    dog.add_task(
        CareTask(
            title="Morning",
            duration_minutes=10,
            priority="medium",
            task_type="general",
            time="08:00",
        )
    )
    dog.add_task(
        CareTask(
            title="Noon",
            duration_minutes=10,
            priority="medium",
            task_type="general",
            time="12:00",
        )
    )
    sched = Scheduler(owner=owner, pet=dog, tasks=[])
    ranked = sched.sort_or_rank_tasks()
    assert [t.title for t in ranked] == ["Morning", "Noon", "Afternoon"]


def test_daily_mark_complete_appends_next_occurrence_with_due_date() -> None:
    pet = Pet(name="Buddy", species="Dog", age=4)
    task = CareTask(
        title="Morning Meds",
        duration_minutes=5,
        priority="high",
        task_type="general",
        frequency="daily",
    )
    pet.add_task(task)
    completion = date(2025, 6, 10)
    new_task = task.mark_complete(pet=pet, as_of=completion)

    assert task.is_completed is True
    assert new_task is not None
    assert new_task.is_completed is False
    assert new_task.due_date == completion + timedelta(days=1)
    assert len(pet.get_tasks()) == 2
    assert pet.get_tasks()[1].title == "Morning Meds"


def test_weekly_mark_complete_adds_seven_days_to_due_date() -> None:
    pet = Pet(name="Mochi", species="Cat", age=2)
    task = CareTask(
        title="Nail Trim",
        duration_minutes=30,
        priority="low",
        task_type="grooming",
        frequency="weekly",
    )
    pet.add_task(task)
    completion = date(2025, 3, 1)
    new_task = task.mark_complete(pet=pet, as_of=completion)

    assert new_task is not None
    assert new_task.due_date == completion + timedelta(days=7)


def test_mark_complete_without_recurring_frequency_returns_none() -> None:
    task = CareTask(
        title="One-off Vet Visit",
        duration_minutes=60,
        priority="high",
        task_type="general",
        frequency="once",
    )
    assert task.mark_complete() is None
    assert task.is_completed is True


def test_recurrence_daily_mark_complete_creates_task_for_following_day() -> None:
    """Marking a daily task complete yields a new instance due the next calendar day."""
    pet = Pet(name="Coco", species="Rabbit", age=1)
    task = CareTask(
        title="Hay refill",
        duration_minutes=10,
        priority="medium",
        task_type="feeding",
        frequency="daily",
    )
    pet.add_task(task)
    completion = date(2025, 12, 31)
    new_task = task.mark_complete(pet=pet, as_of=completion)

    assert new_task is not None
    assert new_task.is_completed is False
    assert new_task.frequency.strip().lower() == "daily"
    assert new_task.due_date == date(2026, 1, 1)
    assert len(pet.get_tasks()) == 2


def test_mark_complete_idempotent_no_duplicate_next_tasks() -> None:
    pet = Pet(name="Buddy", species="Dog", age=4)
    task = CareTask(
        title="Daily",
        duration_minutes=5,
        priority="low",
        task_type="general",
        frequency="daily",
    )
    pet.add_task(task)
    task.mark_complete(pet=pet, as_of=date(2025, 1, 1))
    assert task.mark_complete(pet=pet, as_of=date(2025, 1, 2)) is None
    assert len(pet.get_tasks()) == 2


def test_pet_add_task_increases_task_count() -> None:
    pet = Pet(name="Buddy", species="Dog", age=4)
    initial_count = len(pet.get_tasks())

    task = CareTask(
        title="Evening Walk",
        duration_minutes=20,
        priority="medium",
        task_type="exercise",
        due_window="evening",
    )
    pet.add_task(task)

    assert len(pet.get_tasks()) == initial_count + 1


def test_filter_care_tasks_by_completion_and_pet_name() -> None:
    a = CareTask(
        title="A",
        duration_minutes=5,
        priority="low",
        task_type="general",
        pet_name="Whiskers",
    )
    b = CareTask(
        title="B",
        duration_minutes=5,
        priority="low",
        task_type="general",
        pet_name="Whiskers",
    )
    b.mark_complete()
    c = CareTask(
        title="C",
        duration_minutes=5,
        priority="low",
        task_type="general",
        pet_name="Rex",
    )
    tasks = [a, b, c]

    assert [t.title for t in filter_care_tasks(tasks, is_completed=True)] == ["B"]
    assert [t.title for t in filter_care_tasks(tasks, is_completed=False)] == ["A", "C"]
    assert [t.title for t in filter_care_tasks(tasks, pet_name="whiskers")] == ["A", "B"]
    assert [t.title for t in filter_care_tasks(tasks, is_completed=False, pet_name="Whiskers")] == [
        "A"
    ]


def test_owner_filter_tasks_delegates_to_all_pets() -> None:
    owner = Owner(name="Sam", available_minutes_per_day=120)
    p1 = Pet(name="Whiskers", species="Cat", age=2)
    p2 = Pet(name="Rex", species="Dog", age=5)
    owner.add_pet(p1)
    owner.add_pet(p2)
    t1 = CareTask(
        title="Feed cat",
        duration_minutes=10,
        priority="high",
        task_type="feeding",
        pet_name="Whiskers",
    )
    t2 = CareTask(
        title="Walk dog",
        duration_minutes=20,
        priority="medium",
        task_type="exercise",
        pet_name="Rex",
    )
    t2.mark_complete()
    p1.add_task(t1)
    p2.add_task(t2)

    assert [t.title for t in owner.filter_tasks(pet_name="rex")] == ["Walk dog"]
    assert [t.title for t in owner.filter_tasks(is_completed=True)] == ["Walk dog"]


def test_detect_time_conflicts_empty_for_sequential_generated_plan() -> None:
    owner = Owner(name="Jordan", available_minutes_per_day=60)
    dog = Pet(name="Buddy", species="Dog", age=4)
    owner.add_pet(dog)
    dog.add_task(
        CareTask(
            title="One",
            duration_minutes=15,
            priority="low",
            task_type="general",
            frequency="daily",
        )
    )
    dog.add_task(
        CareTask(
            title="Two",
            duration_minutes=15,
            priority="low",
            task_type="general",
            frequency="daily",
        )
    )
    sched = Scheduler(owner=owner, pet=dog, tasks=[])
    plan = sched.generate_plan(date(2025, 1, 1))
    assert sched.detect_time_conflicts(plan) == []
    assert sched.has_time_conflicts(plan) is False


def test_detect_time_conflicts_adjacent_slots_do_not_overlap() -> None:
    plan = DailyPlan(date=date(2025, 1, 1))
    plan.add_item(
        CareTask(title="A", duration_minutes=10, priority="low", task_type="general"),
        "08:00",
        "08:10",
        "",
    )
    plan.add_item(
        CareTask(title="B", duration_minutes=10, priority="low", task_type="general"),
        "08:10",
        "08:20",
        "",
    )
    owner = Owner(name="x", available_minutes_per_day=60)
    sched = Scheduler(owner=owner, pet=Pet(name="p", species="Dog", age=1), tasks=[])
    assert sched.detect_time_conflicts(plan) == []


def test_detect_time_conflicts_duplicate_identical_slots() -> None:
    """Scheduler reports a conflict when two items use the same start and end times."""
    plan = DailyPlan(date=date(2025, 1, 1))
    t1 = CareTask(title="Walk", duration_minutes=30, priority="low", task_type="exercise")
    t2 = CareTask(title="Train", duration_minutes=30, priority="low", task_type="training")
    plan.add_item(t1, "09:00", "09:30", "")
    plan.add_item(t2, "09:00", "09:30", "")
    owner = Owner(name="x", available_minutes_per_day=120)
    sched = Scheduler(owner=owner, pet=Pet(name="p", species="Dog", age=1), tasks=[])
    assert sched.has_time_conflicts(plan) is True
    conflicts = sched.detect_time_conflicts(plan)
    assert len(conflicts) == 1
    titles = {conflicts[0].first.task.title, conflicts[0].second.task.title}
    assert titles == {"Walk", "Train"}


def test_detect_time_conflicts_overlapping_tasks_same_or_different_pet() -> None:
    plan = DailyPlan(date=date(2025, 1, 1))
    walk = CareTask(
        title="Walk",
        duration_minutes=30,
        priority="low",
        task_type="exercise",
        pet_name="Buddy",
    )
    feed = CareTask(
        title="Feed",
        duration_minutes=15,
        priority="low",
        task_type="feeding",
        pet_name="Mochi",
    )
    plan.add_item(walk, "09:00", "09:30", "")
    plan.add_item(feed, "09:15", "09:30", "")
    owner = Owner(name="x", available_minutes_per_day=120)
    sched = Scheduler(owner=owner, pet=Pet(name="p", species="Dog", age=1), tasks=[])
    conflicts = sched.detect_time_conflicts(plan)
    assert len(conflicts) == 1
    pair = {conflicts[0].first.task.title, conflicts[0].second.task.title}
    assert pair == {"Walk", "Feed"}
    assert sched.has_time_conflicts(plan) is True


def test_scheduling_conflict_warning_is_none_when_clear() -> None:
    owner = Owner(name="Jordan", available_minutes_per_day=60)
    dog = Pet(name="Buddy", species="Dog", age=4)
    owner.add_pet(dog)
    dog.add_task(
        CareTask(
            title="One",
            duration_minutes=15,
            priority="low",
            task_type="general",
            frequency="daily",
        )
    )
    sched = Scheduler(owner=owner, pet=dog, tasks=[])
    plan = sched.generate_plan(date(2025, 1, 1))
    assert sched.scheduling_conflict_warning(plan) is None


def test_scheduling_conflict_warning_message_on_overlap() -> None:
    plan = DailyPlan(date=date(2025, 1, 1))
    plan.add_item(
        CareTask(title="A", duration_minutes=30, priority="low", task_type="general", pet_name="X"),
        "09:00",
        "09:30",
        "",
    )
    plan.add_item(
        CareTask(title="B", duration_minutes=15, priority="low", task_type="general", pet_name="Y"),
        "09:15",
        "09:30",
        "",
    )
    owner = Owner(name="x", available_minutes_per_day=120)
    sched = Scheduler(owner=owner, pet=Pet(name="p", species="Dog", age=1), tasks=[])
    msg = sched.scheduling_conflict_warning(plan)
    assert msg is not None
    assert "Warning:" in msg
    assert "overlap" in msg.lower()
    assert "A" in msg and "B" in msg


def test_scheduling_conflict_warning_never_raises_on_bad_times() -> None:
    plan = DailyPlan(date=date(2025, 1, 1))
    plan.add_item(
        CareTask(title="Bad", duration_minutes=5, priority="low", task_type="general"),
        "not-a-time",
        "08:00",
        "",
    )
    plan.add_item(
        CareTask(title="Other", duration_minutes=5, priority="low", task_type="general"),
        "09:00",
        "09:05",
        "",
    )
    owner = Owner(name="x", available_minutes_per_day=60)
    sched = Scheduler(owner=owner, pet=Pet(name="p", species="Dog", age=1), tasks=[])
    msg = sched.scheduling_conflict_warning(plan)
    assert msg is not None
    assert "could not verify" in msg.lower()
