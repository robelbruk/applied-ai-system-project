from datetime import date
from typing import Any, Dict, List

import streamlit as st

from pawpal_system import CareTask, Owner, Pet, Scheduler

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")

st.markdown(
    """
**PawPal+** plans pet care for the day: it **ranks** tasks, **filters** what is feasible,
builds a **timeline**, and **checks for time overlaps**. Use the panels below to register a profile,
add tasks, inspect how the scheduler orders work, then generate a plan.
"""
)

with st.expander("What the scheduler does", expanded=False):
    st.markdown(
        """
- **Feasible tasks** — skips completed tasks, owner-excluded types, and tasks whose due window
  conflicts with availability.
- **Ranking** — orders by time-of-day hints, required vs optional, priority, then duration.
- **Conflicts** — after building the plan, warns if any scheduled intervals overlap (should be
  rare for the default sequential planner).
"""
    )

st.divider()

if "owner" not in st.session_state:
    st.session_state.owner = None
if "current_pet" not in st.session_state:
    st.session_state.current_pet = None

st.subheader("Owner & pet")
st.caption("Register once, then add tasks below. Data is kept in `st.session_state` across reruns.")

owner_name = st.text_input("Owner name", value="Jordan")
owner_minutes = st.number_input(
    "Available minutes per day", min_value=15, max_value=1440, value=120, step=15
)
pet_name = st.text_input("Pet name", value="Mochi")
species = st.selectbox("Species", ["dog", "cat", "other"])
pet_age = st.number_input("Pet age (years)", min_value=0, max_value=40, value=3)

if st.button("Register owner & pet"):
    owner = Owner(name=owner_name, available_minutes_per_day=int(owner_minutes))
    pet = Pet(name=pet_name, species=species, age=int(pet_age))
    owner.add_pet(pet)
    st.session_state.owner = owner
    st.session_state.current_pet = pet
    st.success(f"Registered {owner.name} and {pet.name}.")

if st.session_state.owner and st.session_state.current_pet:
    o = st.session_state.owner
    p = st.session_state.current_pet
    st.info(
        f"Active profile: **{o.name}** ({o.get_daily_capacity()} min/day) · "
        f"**{p.name}** ({p.species}, age {p.age})"
    )

st.markdown("### Tasks")
st.caption("Tasks live on the pet; the scheduler ranks and filters them when you preview or generate.")

col1, col2, col3, col4 = st.columns(4)
with col1:
    task_title = st.text_input("Task title", value="Morning walk")
with col2:
    duration = st.number_input("Duration (minutes)", min_value=1, max_value=240, value=20)
with col3:
    priority = st.selectbox("Priority", ["low", "medium", "high"], index=2)
with col4:
    task_type = st.selectbox(
        "Task type",
        ["exercise", "feeding", "grooming", "general"],
        index=0,
    )

if st.button("Add task"):
    if st.session_state.owner is None or st.session_state.current_pet is None:
        st.error("Register an owner and pet first.")
    else:
        task = CareTask(
            title=task_title,
            duration_minutes=int(duration),
            priority=priority,
            task_type=task_type,
        )
        st.session_state.current_pet.add_task(task)
        st.success(f"Added “{task.title}” for {st.session_state.current_pet.name}.")

tasks_for_display: List[Dict[str, Any]] = []
if st.session_state.owner and st.session_state.current_pet:
    for t in st.session_state.current_pet.get_tasks():
        tasks_for_display.append(
            {
                "title": t.title,
                "duration_minutes": t.duration_minutes,
                "priority": t.priority,
                "task_type": t.task_type,
                "description": t.describe(),
            }
        )

if tasks_for_display:
    st.markdown("**Current tasks (as stored)**")
    st.table(tasks_for_display)
else:
    st.info("No tasks yet. Register a pet and add one above.")

# Scheduler preview: ranking + feasibility (Phase 3 logic surfaced in the UI)
if st.session_state.owner and st.session_state.current_pet and st.session_state.current_pet.get_tasks():
    owner = st.session_state.owner
    pet = st.session_state.current_pet
    scheduler = Scheduler(owner=owner, pet=pet, tasks=pet.get_tasks())

    feasible = scheduler.filter_feasible_tasks()
    feasible_ids = {id(t) for t in feasible}
    pool = owner.get_all_tasks() or list(pet.get_tasks())
    not_feasible = [t for t in pool if id(t) not in feasible_ids]

    st.markdown("### Scheduling preview")
    st.caption("Uses `Scheduler.filter_feasible_tasks` and `Scheduler.sort_or_rank_tasks`.")

    st.success(
        f"**{len(feasible)}** feasible task(s) for today — these are the ones the planner considers."
    )
    if not_feasible:
        st.warning(
            f"**{len(not_feasible)}** task(s) filtered out (completed, excluded type, or "
            "due window vs owner availability)."
        )
        st.table(
            [
                {
                    "title": t.title,
                    "duration_minutes": t.duration_minutes,
                    "priority": t.priority,
                    "task_type": t.task_type,
                    "completed": t.is_completed,
                }
                for t in not_feasible
            ]
        )

    ranked_rows: List[Dict[str, Any]] = []
    for i, t in enumerate(scheduler.sort_or_rank_tasks(), start=1):
        ranked_rows.append(
            {
                "order": i,
                "title": t.title,
                "duration_min": t.duration_minutes,
                "priority": t.priority,
                "required": "yes" if t.is_required else "no",
                "task_type": t.task_type,
                "time_hint": t.time or "—",
                "due_window": t.due_window or "—",
            }
        )
    st.markdown("**Processing order** (how tasks will be considered when you generate a schedule)")
    st.table(ranked_rows)

st.divider()

st.subheader("Build schedule")
st.caption("Uses `Scheduler.generate_plan` with your owner, pet, and tasks.")

if st.button("Generate schedule"):
    if st.session_state.owner is None or st.session_state.current_pet is None:
        st.error("Register an owner and pet first.")
    elif not st.session_state.current_pet.get_tasks():
        st.warning("Add at least one task before generating a schedule.")
    else:
        owner = st.session_state.owner
        pet = st.session_state.current_pet
        scheduler = Scheduler(owner=owner, pet=pet, tasks=pet.get_tasks())
        plan = scheduler.generate_plan(date.today())

        st.success(f"Plan for **{plan.date.isoformat()}** · **{plan.total_minutes()}** min scheduled")

        conflict_msg = scheduler.scheduling_conflict_warning(plan)
        if conflict_msg:
            st.warning(conflict_msg)
        elif plan.scheduled_items:
            st.success("No overlapping time slots detected — intervals look consistent.")

        if plan.scheduled_items:
            st.markdown("**Timeline**")
            st.table(plan.to_display_rows())

            explanations = scheduler.build_explanations(plan)
            if explanations:
                st.markdown("**Decisions**")
                st.table(
                    [{"task": title, "explanation": text} for title, text in explanations.items()]
                )
        else:
            st.info("No tasks fit in the schedule with the current settings.")

        if plan.unscheduled_tasks:
            st.subheader("Unscheduled")
            st.table(
                [
                    {
                        "title": t.title,
                        "duration_min": t.duration_minutes,
                        "priority": t.priority,
                    }
                    for t in plan.unscheduled_tasks
                ]
            )
            st.warning(
                f"{len(plan.unscheduled_tasks)} task(s) did not fit in the remaining time budget."
            )

        with st.expander("Full plan text"):
            st.text(plan.explain())
