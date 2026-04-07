"""Workout program generation and session debrief via AI coaches."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import anthropic
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import UserProfile
from app.models.workout import WorkoutProgram, WorkoutSession, WorkoutSet
from app.services.coaches import get_coach
from app.services.knowledge import get_relevant_knowledge

logger = structlog.get_logger()

PROGRAM_GENERATION_PROMPT = """You are a fitness coach creating a structured workout program.

Based on the user's profile, generate a complete training program as valid JSON.

The JSON MUST follow this exact structure:
{{
  "name": "Program Name",
  "coach_note": "A training note that appears at the top of the user's Program page. Set the tone for this phase — what to focus on, key priorities, motivational context. 2-4 sentences.",
  "days": [
    {{
      "id": "unique-day-id",
      "name": "Day Name",
      "day_label": "Monday",
      "exercises": [
        {{
          "id": "unique-exercise-id",
          "name": "Exercise Name",
          "sets": 4,
          "rep_range": "6-8",
          "description": "Brief description of the movement and technique.",
          "muscles_targeted": ["primary muscle", "secondary muscle"],
          "muscles_warning": "What you should NOT feel and why — e.g. Don't feel this in your lower back",
          "form_cues": "Key form points. Comma separated.",
          "youtube_search": "exercise name form guide"
        }}
      ]
    }}
  ]
}}

Rules:
1. Return ONLY valid JSON — no markdown, no explanation, no code fences
2. Every exercise must have ALL fields filled in — no nulls, no empty strings
3. Use unique IDs for days and exercises (e.g., "day-upper", "ex-bench-press")
4. Include 4-7 exercises per day
5. Include both compound and isolation movements
6. Set rep_range appropriate to the goal (strength: 4-6, hypertrophy: 8-12, endurance: 12-15)
"""

DEBRIEF_PROMPT = """You just finished coaching a workout session. Review the data and give a short debrief.

Session data:
{session_data}

Previous session for comparison (if available):
{previous_data}

Rules:
1. Reference specific exercises and weights from the session
2. Call out any PRs or weight increases with enthusiasm
3. Note any drops in weight or reps — ask how it felt, don't criticize
4. Keep it to 3-5 sentences
5. End with a forward-looking comment or question about next session
"""


async def generate_program(
    db: AsyncSession,
    user_id: uuid.UUID,
    coach_id: str,
) -> WorkoutProgram:
    """Ask the AI coach to generate a workout program."""
    coach = get_coach(coach_id)
    if not coach:
        raise ValueError(f"Unknown coach: {coach_id}")

    # Load user profile
    stmt = select(UserProfile).where(UserProfile.user_id == user_id)
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()
    profile_text = profile.context if profile else "No profile available."

    system = PROGRAM_GENERATION_PROMPT
    if coach.get("system_addendum"):
        system += f"\n\n{coach['system_addendum']}"

    # Inject domain knowledge relevant to program generation
    knowledge = get_relevant_knowledge(
        f"workout program {profile_text[:200]}",
        max_modules=3,
    )
    if knowledge:
        system += f"\n{knowledge}"

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": f"Create a program for this person:\n\n{profile_text}"}],
    )

    raw = response.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

    program_data = json.loads(raw)
    program_name = program_data.pop("name", "Training Program")
    coach_note = program_data.pop("coach_note", "")

    # Deactivate existing programs
    existing = await db.execute(
        select(WorkoutProgram).where(
            WorkoutProgram.user_id == user_id, WorkoutProgram.active.is_(True)
        )
    )
    for prog in existing.scalars():
        prog.active = False

    program = WorkoutProgram(
        user_id=user_id,
        coach_id=coach_id,
        name=program_name,
        coach_note=coach_note,
        active=True,
        program_data=program_data,
    )
    db.add(program)
    await db.flush()
    return program


async def generate_debrief(
    db: AsyncSession,
    session: WorkoutSession,
    coach_id: str,
) -> str:
    """Generate a coach debrief after a completed workout."""
    coach = get_coach(coach_id)

    # Build session data summary
    sets = session.sets
    exercise_summary = {}
    for s in sets:
        if s.exercise_id not in exercise_summary:
            exercise_summary[s.exercise_id] = []
        exercise_summary[s.exercise_id].append(
            {"set": s.set_number, "weight_kg": s.weight_kg, "reps": s.reps}
        )

    session_data = json.dumps(exercise_summary, indent=2)

    # Load previous session for same day
    stmt = (
        select(WorkoutSession)
        .where(
            WorkoutSession.user_id == session.user_id,
            WorkoutSession.day_id == session.day_id,
            WorkoutSession.finished_at.is_not(None),
            WorkoutSession.id != session.id,
        )
        .order_by(WorkoutSession.finished_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    prev_session = result.scalar_one_or_none()

    previous_data = "No previous session for this day."
    if prev_session:
        prev_sets = {}
        for s in prev_session.sets:
            if s.exercise_id not in prev_sets:
                prev_sets[s.exercise_id] = []
            prev_sets[s.exercise_id].append(
                {"set": s.set_number, "weight_kg": s.weight_kg, "reps": s.reps}
            )
        previous_data = json.dumps(prev_sets, indent=2)

    system = DEBRIEF_PROMPT.format(session_data=session_data, previous_data=previous_data)
    if coach and coach.get("system_addendum"):
        system += f"\n\n{coach['system_addendum']}"

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=512,
        system=system,
        messages=[{"role": "user", "content": "Give me my post-workout debrief."}],
    )
    return response.content[0].text


async def get_exercise_history(
    db: AsyncSession,
    user_id: uuid.UUID,
    exercise_id: str,
    limit: int = 20,
) -> list[dict]:
    """Get weight progression for a specific exercise across sessions."""
    stmt = (
        select(WorkoutSet, WorkoutSession.started_at)
        .join(WorkoutSession, WorkoutSet.session_id == WorkoutSession.id)
        .where(
            WorkoutSession.user_id == user_id,
            WorkoutSet.exercise_id == exercise_id,
            WorkoutSession.finished_at.is_not(None),
        )
        .order_by(WorkoutSession.started_at.desc(), WorkoutSet.set_number)
        .limit(limit * 10)
    )
    result = await db.execute(stmt)
    rows = result.all()

    # Group by session date
    sessions: dict[str, list[dict]] = {}
    for ws, started_at in rows:
        date_str = started_at.strftime("%Y-%m-%d")
        if date_str not in sessions:
            sessions[date_str] = []
        sessions[date_str].append({
            "set": ws.set_number,
            "weight_kg": ws.weight_kg,
            "reps": ws.reps,
        })

    return [
        {"date": date, "sets": sets}
        for date, sets in list(sessions.items())[:limit]
    ]


async def get_last_weights(
    db: AsyncSession,
    user_id: uuid.UUID,
    day_id: str,
) -> dict[str, float]:
    """Get last logged weight per exercise for a given day. Returns {exercise_id: weight_kg}."""
    stmt = (
        select(WorkoutSession)
        .where(
            WorkoutSession.user_id == user_id,
            WorkoutSession.day_id == day_id,
            WorkoutSession.finished_at.is_not(None),
        )
        .order_by(WorkoutSession.finished_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    prev = result.scalar_one_or_none()

    if not prev:
        return {}

    # Get the max weight per exercise from that session
    weights: dict[str, float] = {}
    for s in prev.sets:
        if s.exercise_id not in weights or s.weight_kg > weights[s.exercise_id]:
            weights[s.exercise_id] = s.weight_kg
    return weights
