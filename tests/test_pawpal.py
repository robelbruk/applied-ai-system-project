from pawpal_system import CareTask, Pet


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
