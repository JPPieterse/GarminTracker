"""Workout program and session tracking endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.workout import WorkoutProgram, WorkoutSession, WorkoutSet
from app.services import workout as workout_service

router = APIRouter(prefix="/workout", tags=["workout"])


# ── Schemas ──────────────────────────────────────────────────────────────────


class GenerateProgramRequest(BaseModel):
    coach: str


class StartWorkoutRequest(BaseModel):
    day_id: str


class LogSetRequest(BaseModel):
    exercise_id: str
    set_number: int
    weight_kg: float
    reps: int


# ── Program Endpoints ────────────────────────────────────────────────────────


@router.get("/program")
async def get_active_program(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the user's active workout program."""
    stmt = select(WorkoutProgram).where(
        WorkoutProgram.user_id == user.id, WorkoutProgram.active.is_(True)
    )
    result = await db.execute(stmt)
    program = result.scalar_one_or_none()

    if not program:
        return {"program": None}

    return {
        "program": {
            "id": str(program.id),
            "name": program.name,
            "coach_id": program.coach_id,
            "program_data": program.program_data,
            "created_at": program.created_at.isoformat(),
        }
    }


@router.post("/program/generate")
async def generate_program(
    body: GenerateProgramRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ask the AI coach to generate a new workout program."""
    program = await workout_service.generate_program(db, user.id, body.coach)
    return {
        "program": {
            "id": str(program.id),
            "name": program.name,
            "coach_id": program.coach_id,
            "program_data": program.program_data,
        }
    }


# ── Session Endpoints ────────────────────────────────────────────────────────


@router.post("/start")
async def start_workout(
    body: StartWorkoutRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start a new workout session for a given program day."""
    stmt = select(WorkoutProgram).where(
        WorkoutProgram.user_id == user.id, WorkoutProgram.active.is_(True)
    )
    result = await db.execute(stmt)
    program = result.scalar_one_or_none()
    if not program:
        raise HTTPException(status_code=404, detail="No active program")

    day_ids = [d["id"] for d in program.program_data.get("days", [])]
    if body.day_id not in day_ids:
        raise HTTPException(status_code=400, detail=f"Day '{body.day_id}' not in program")

    session = WorkoutSession(
        user_id=user.id,
        program_id=program.id,
        day_id=body.day_id,
        started_at=datetime.now(timezone.utc),
    )
    db.add(session)
    await db.flush()

    last_weights = await workout_service.get_last_weights(db, user.id, body.day_id)

    return {
        "session_id": str(session.id),
        "day_id": session.day_id,
        "last_weights": last_weights,
    }


@router.get("/session/{session_id}")
async def get_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a workout session with all logged sets."""
    import uuid as _uuid
    stmt = select(WorkoutSession).where(
        WorkoutSession.id == _uuid.UUID(session_id),
        WorkoutSession.user_id == user.id,
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    sets_data = [
        {
            "exercise_id": s.exercise_id,
            "set_number": s.set_number,
            "weight_kg": s.weight_kg,
            "reps": s.reps,
            "logged_at": s.logged_at.isoformat() if s.logged_at else None,
        }
        for s in session.sets
    ]

    return {
        "id": str(session.id),
        "day_id": session.day_id,
        "started_at": session.started_at.isoformat(),
        "finished_at": session.finished_at.isoformat() if session.finished_at else None,
        "coach_debrief": session.coach_debrief,
        "sets": sets_data,
    }


@router.post("/session/{session_id}/log")
async def log_set(
    session_id: str,
    body: LogSetRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Log a single set within a workout session."""
    import uuid as _uuid
    stmt = select(WorkoutSession).where(
        WorkoutSession.id == _uuid.UUID(session_id),
        WorkoutSession.user_id == user.id,
        WorkoutSession.finished_at.is_(None),
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Active session not found")

    ws = WorkoutSet(
        session_id=session.id,
        exercise_id=body.exercise_id,
        set_number=body.set_number,
        weight_kg=body.weight_kg,
        reps=body.reps,
        logged_at=datetime.now(timezone.utc),
    )
    db.add(ws)
    await db.flush()

    return {
        "id": str(ws.id),
        "exercise_id": ws.exercise_id,
        "set_number": ws.set_number,
        "weight_kg": ws.weight_kg,
        "reps": ws.reps,
    }


@router.post("/session/{session_id}/complete")
async def complete_workout(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Complete a workout session and generate coach debrief."""
    import uuid as _uuid
    stmt = select(WorkoutSession).where(
        WorkoutSession.id == _uuid.UUID(session_id),
        WorkoutSession.user_id == user.id,
        WorkoutSession.finished_at.is_(None),
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Active session not found")

    session.finished_at = datetime.now(timezone.utc)

    prog_stmt = select(WorkoutProgram).where(WorkoutProgram.id == session.program_id)
    prog_result = await db.execute(prog_stmt)
    program = prog_result.scalar_one()

    try:
        debrief = await workout_service.generate_debrief(db, session, program.coach_id)
        session.coach_debrief = debrief
    except Exception:
        session.coach_debrief = "Great workout! Let's chat about how it went."

    await db.flush()

    duration_min = None
    if session.started_at and session.finished_at:
        duration_min = round((session.finished_at - session.started_at).total_seconds() / 60)

    return {
        "status": "completed",
        "duration_min": duration_min,
        "total_sets": len(session.sets),
        "coach_debrief": session.coach_debrief,
    }


@router.get("/history")
async def workout_history(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get past workout sessions."""
    stmt = (
        select(WorkoutSession)
        .where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.finished_at.is_not(None),
        )
        .order_by(WorkoutSession.finished_at.desc())
        .limit(30)
    )
    result = await db.execute(stmt)
    sessions = result.scalars().all()

    return [
        {
            "id": str(s.id),
            "day_id": s.day_id,
            "started_at": s.started_at.isoformat(),
            "finished_at": s.finished_at.isoformat() if s.finished_at else None,
            "total_sets": len(s.sets),
        }
        for s in sessions
    ]


@router.get("/exercise/{exercise_id}/history")
async def exercise_history(
    exercise_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get weight progression for a specific exercise."""
    history = await workout_service.get_exercise_history(db, user.id, exercise_id)
    return history
