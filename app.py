import os
from datetime import date
from typing import Any, Dict, List

import streamlit as st

from pawpal_system import CareTask, Owner, Pet, Scheduler

# Side-effect import: loads .env (HF_TOKEN, etc.) before any AI module is touched.
import ai  # noqa: F401

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
if "architect_trace" not in st.session_state:
    st.session_state.architect_trace = None
if "ai_flash" not in st.session_state:
    st.session_state.ai_flash = None

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

st.divider()
st.subheader("🤖 Describe your day (Care Plan Architect)")
st.caption(
    "Paste a natural-language description. The architect extracts structured tasks, "
    "validates them, previews a schedule, and runs a self-critique — all without modifying "
    "your saved tasks below."
)

if st.session_state.ai_flash:
    st.success(st.session_state.ai_flash)
    st.session_state.ai_flash = None

if not os.environ.get("HF_TOKEN"):
    st.warning(
        "`HF_TOKEN` is not set. Copy `.env.example` to `.env` and add your Hugging Face token "
        "to enable the AI intake (the manual form below still works)."
    )
else:
    nl_default = (
        "My dog Buddy needs a 25-min morning walk and breakfast at 8am (required). "
        "Mochi the cat should get a 15-min evening brushing."
    )
    nl_text = st.text_area("What does today look like?", value=nl_default, height=120)

    if st.button("🪄 Draft plan with AI"):
        if st.session_state.owner is None or st.session_state.current_pet is None:
            st.error("Register an owner and pet first.")
        else:
            # Clone owner + pet into disposable objects so architect doesn't mutate
            # the session-state pet's task list. Saved tasks come from the explicit
            # commit step below.
            real_owner = st.session_state.owner
            real_pet = st.session_state.current_pet
            tmp_owner = Owner(
                name=real_owner.name,
                available_minutes_per_day=real_owner.get_daily_capacity(),
                preferences=dict(real_owner.preferences),
            )
            tmp_pet = Pet(
                name=real_pet.name,
                species=real_pet.species,
                age=real_pet.age,
                special_needs=list(real_pet.special_needs),
            )
            tmp_owner.add_pet(tmp_pet)

            with st.spinner("Calling the architect..."):
                from ai.architect import CarePlanArchitect

                try:
                    architect = CarePlanArchitect()
                    trace = architect.run(nl_text, tmp_owner, tmp_pet)
                except Exception as exc:  # network, auth, etc.
                    st.error(f"Architect call failed: {exc}")
                    trace = None

            if trace is not None:
                # Clear any stale per-draft selection toggles from a previous run.
                for key in [k for k in st.session_state if k.startswith("draft_select_")]:
                    del st.session_state[key]
                st.session_state.architect_trace = trace

    # Render the persisted trace across reruns so Save/Discard can act on it.
    trace = st.session_state.architect_trace
    if trace is not None:
        if trace.error:
            st.error(f"Architect error: {trace.error}")

        if trace.critic is not None:
            conf = trace.critic.confidence
            if conf >= 0.8:
                st.success(f"Critic confidence: {conf:.2f} ✅")
            elif conf >= 0.5:
                st.warning(f"Critic confidence: {conf:.2f} ⚠️")
            else:
                st.error(f"Critic confidence: {conf:.2f} ❌")

        active_pet = st.session_state.current_pet
        if trace.drafts:
            st.markdown(
                f"**Drafted tasks** — select which to save to **{active_pet.name}** if you like the plan."
            )
            st.caption(
                "All drafts are selected by default. Saving coerces each task's pet to the active pet."
            )
            for i, d in enumerate(trace.drafts):
                when = d.time or d.due_window or "anytime"
                pet_label = (
                    f"→ {d.pet_name}"
                    if d.pet_name and d.pet_name.lower() != active_pet.name.lower()
                    else ""
                )
                label = (
                    f"**{d.title}** · {d.duration_minutes} min · "
                    f"{d.priority} · {d.task_type} · {when}"
                    f"{' · required' if d.is_required else ''}"
                    f"{' · ' + pet_label if pet_label else ''}"
                )
                st.checkbox(label, value=True, key=f"draft_select_{i}")

        if trace.validation_errors:
            st.markdown("**Validation issues** (auto-recovered via retry if possible)")
            for err in trace.validation_errors:
                st.code(err, language="text")

        if trace.plan and trace.plan.scheduled_items:
            st.markdown("**Previewed schedule**")
            st.table(trace.plan.to_display_rows())
            if trace.conflict_warning:
                st.warning(trace.conflict_warning)
            else:
                st.success("No scheduling conflicts detected.")
        elif trace.plan and not trace.plan.scheduled_items:
            st.info("Plan generated but no tasks fit in the owner's capacity.")

        if trace.critic is not None and trace.critic.issues:
            st.markdown("**Critic report**")
            st.table(
                [
                    {
                        "severity": i.severity,
                        "category": i.category,
                        "message": i.message,
                    }
                    for i in trace.critic.issues
                ]
            )

        with st.expander("Raw LLM output + retry count", expanded=False):
            st.caption(f"retries: {trace.retry_count}")
            st.code(trace.raw_llm_output or "(empty)", language="json")

        if trace.drafts and active_pet is not None:
            selected_indices = [
                i
                for i in range(len(trace.drafts))
                if st.session_state.get(f"draft_select_{i}", True)
            ]
            save_col, discard_col = st.columns([3, 1])
            save_clicked = save_col.button(
                f"💾 Save {len(selected_indices)} of {len(trace.drafts)} task(s) to {active_pet.name}",
                disabled=len(selected_indices) == 0,
                type="primary",
            )
            discard_clicked = discard_col.button("🗑️ Discard draft")

            if save_clicked:
                saved = 0
                for i in selected_indices:
                    draft = trace.drafts[i]
                    task = draft.to_care_task()
                    task.pet_name = active_pet.name
                    active_pet.add_task(task)
                    saved += 1
                st.session_state.architect_trace = None
                for key in [k for k in st.session_state if k.startswith("draft_select_")]:
                    del st.session_state[key]
                st.session_state.ai_flash = (
                    f"Added {saved} AI-drafted task(s) to {active_pet.name}. "
                    "Scroll down to generate a schedule."
                )
                st.rerun()

            if discard_clicked:
                st.session_state.architect_trace = None
                for key in [k for k in st.session_state if k.startswith("draft_select_")]:
                    del st.session_state[key]
                st.session_state.ai_flash = "Discarded the AI draft."
                st.rerun()

st.divider()
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
