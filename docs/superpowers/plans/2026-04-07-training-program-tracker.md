# Training Program Tracker — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a gym-ready workout tracker where AI coaches generate programs, users log sets/reps/weights mid-workout, and the coach debriefs after each session.

**Architecture:** Three new SQLAlchemy models (WorkoutProgram, WorkoutSession, WorkoutSet) in a new `workout.py` model file. A new `workout.py` service handles program generation and debrief via the Anthropic API. A new `workout.py` API router exposes 7 endpoints. Three new frontend pages (program overview, active workout, focused exercise view) under `frontend/app/dashboard/program/`.

**Tech Stack:** FastAPI, SQLAlchemy (SQLite), Anthropic Claude Sonnet 4, Next.js 14, Tailwind CSS, Framer Motion, Lucide icons.

---

## File Structure

### Backend — New Files
| File | Responsibility |
|------|---------------|
| `backend/app/models/workout.py` | WorkoutProgram, WorkoutSession, WorkoutSet models |
| `backend/app/services/workout.py` | Program generation prompt, debrief generation, exercise history queries |
| `backend/app/api/workout.py` | 7 REST endpoints for programs, sessions, set logging |
| `backend/tests/test_workout_api.py` | API endpoint tests |

### Backend — Modified Files
| File | Change |
|------|--------|
| `backend/app/main.py` | Register workout router |

### Frontend — New Files
| File | Responsibility |
|------|---------------|
| `frontend/app/dashboard/program/page.tsx` | Program overview — day cards, empty state |
| `frontend/app/dashboard/program/workout/[sessionId]/page.tsx` | Active workout — compact list + focused view |
| `frontend/lib/workout-api.ts` | API client functions for workout endpoints |

### Frontend — Modified Files
| File | Change |
|------|--------|
| `frontend/components/shared/Sidebar.tsx` | Add "Program" nav item |
| `frontend/lib/types.ts` | Add workout-related TypeScript interfaces |

---

## Task 1: Backend Models

**Files:**
- Create: `backend/app/models/workout.py`
- Test: `backend/tests/test_workout_api.py` (model import test only)

- [ ] **Step 1: Create workout models**

Create `backend/app/models/workout.py`:

```python
"""Workout program, session, and set tracking models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class WorkoutProgram(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "workout_programs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    coach_id: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(256), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    program_data: Mapped[dict] = mapped_column(JSON, default=dict)

    sessions: Mapped[list[WorkoutSession]] = relationship(
        back_populates="program", cascade="all, delete-orphan"
    )


class WorkoutSession(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "workout_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    program_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workout_programs.id", ondelete="CASCADE"), index=True
    )
    day_id: Mapped[str] = mapped_column(String(128))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    coach_debrief: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    program: Mapped[WorkoutProgram] = relationship(back_populates="sessions")
    sets: Mapped[list[WorkoutSet]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class WorkoutSet(UUIDMixin, Base):
    __tablename__ = "workout_sets"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workout_sessions.id", ondelete="CASCADE"), index=True
    )
    exercise_id: Mapped[str] = mapped_column(String(128))
    set_number: Mapped[int] = mapped_column(Integer)
    weight_kg: Mapped[float] = mapped_column(Float)
    reps: Mapped[int] = mapped_column(Integer)
    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(__import__("datetime").timezone.utc),
    )

    session: Mapped[WorkoutSession] = relationship(back_populates="sets")
```

- [ ] **Step 2: Register models in main.py for auto-create**

In `backend/app/main.py`, inside the `_create_tables` function, add after the existing model imports:

```python
        import app.models.workout  # noqa: F401
```

Add it after the line `import app.models.sharing  # noqa: F401`.

- [ ] **Step 3: Verify models load**

Run:
```bash
cd backend && .venv/Scripts/python -c "from app.models.workout import WorkoutProgram, WorkoutSession, WorkoutSet; print('Models OK')"
```
Expected: `Models OK`

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/workout.py backend/app/main.py
git commit -m "feat(workout): add WorkoutProgram, WorkoutSession, WorkoutSet models"
```

---

## Task 2: Workout Service — Program Generation

**Files:**
- Create: `backend/app/services/workout.py`

- [ ] **Step 1: Create workout service with program generation**

Create `backend/app/services/workout.py`:

```python
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

logger = structlog.get_logger()

PROGRAM_GENERATION_PROMPT = """You are a fitness coach creating a structured workout program.

Based on the user's profile, generate a complete training program as valid JSON.

The JSON MUST follow this exact structure:
{{
  "name": "Program Name",
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
```

- [ ] **Step 2: Verify service imports**

Run:
```bash
cd backend && .venv/Scripts/python -c "from app.services.workout import generate_program, generate_debrief, get_exercise_history, get_last_weights; print('Service OK')"
```
Expected: `Service OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/workout.py
git commit -m "feat(workout): add program generation, debrief, and exercise history service"
```

---

## Task 3: Workout API Router

**Files:**
- Create: `backend/app/api/workout.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create workout API router**

Create `backend/app/api/workout.py`:

```python
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
    # Get active program
    stmt = select(WorkoutProgram).where(
        WorkoutProgram.user_id == user.id, WorkoutProgram.active.is_(True)
    )
    result = await db.execute(stmt)
    program = result.scalar_one_or_none()
    if not program:
        raise HTTPException(status_code=404, detail="No active program")

    # Verify day_id exists in program
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

    # Get last weights for pre-filling
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

    # Get coach_id from program
    prog_stmt = select(WorkoutProgram).where(WorkoutProgram.id == session.program_id)
    prog_result = await db.execute(prog_stmt)
    program = prog_result.scalar_one()

    # Generate debrief
    try:
        debrief = await workout_service.generate_debrief(db, session, program.coach_id)
        session.coach_debrief = debrief
    except Exception as exc:
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
```

- [ ] **Step 2: Register router in main.py**

In `backend/app/main.py`, add after the existing router imports (around line 54):

```python
    from app.api.workout import router as workout_router
```

And add after the existing `app.include_router` calls (around line 61):

```python
    app.include_router(workout_router, prefix="/api")
```

- [ ] **Step 3: Restart server and test endpoints**

Run:
```bash
# Kill existing server, restart
taskkill //F //IM python.exe 2>/dev/null
sleep 2
cd backend && .venv/Scripts/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
sleep 5

# Test program endpoint (should return null program)
TOKEN=$(.venv/Scripts/python -c "from dotenv import load_dotenv; load_dotenv(); from app.core.security import create_access_token; print(create_access_token('fbc1e205-68f2-4426-9edf-9a8bf3100f0f','test','test'))")
curl -s http://localhost:8000/api/workout/program -H "Authorization: Bearer $TOKEN"
```

Expected: `{"program":null}`

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/workout.py backend/app/main.py
git commit -m "feat(workout): add workout API router with 7 endpoints"
```

---

## Task 4: Frontend Types and API Client

**Files:**
- Modify: `frontend/lib/types.ts`
- Create: `frontend/lib/workout-api.ts`

- [ ] **Step 1: Add TypeScript interfaces**

Add to the bottom of `frontend/lib/types.ts`:

```typescript
// ── Workout Program Tracker ─────────────────────────────────────────────

export interface ProgramExercise {
  id: string;
  name: string;
  sets: number;
  rep_range: string;
  description: string;
  muscles_targeted: string[];
  muscles_warning: string;
  form_cues: string;
  youtube_search: string;
}

export interface ProgramDay {
  id: string;
  name: string;
  day_label: string;
  exercises: ProgramExercise[];
}

export interface WorkoutProgram {
  id: string;
  name: string;
  coach_id: string;
  program_data: { days: ProgramDay[] };
  created_at?: string;
}

export interface LoggedSet {
  exercise_id: string;
  set_number: number;
  weight_kg: number;
  reps: number;
  logged_at?: string;
}

export interface WorkoutSessionData {
  id: string;
  day_id: string;
  started_at: string;
  finished_at: string | null;
  coach_debrief: string | null;
  sets: LoggedSet[];
}

export interface StartWorkoutResponse {
  session_id: string;
  day_id: string;
  last_weights: Record<string, number>;
}

export interface CompleteWorkoutResponse {
  status: string;
  duration_min: number | null;
  total_sets: number;
  coach_debrief: string;
}

export interface ExerciseHistoryEntry {
  date: string;
  sets: { set: number; weight_kg: number; reps: number }[];
}
```

- [ ] **Step 2: Create workout API client**

Create `frontend/lib/workout-api.ts`:

```typescript
import type {
  WorkoutProgram,
  StartWorkoutResponse,
  WorkoutSessionData,
  LoggedSet,
  CompleteWorkoutResponse,
  ExerciseHistoryEntry,
} from "./types";

async function fetchApi<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("token") : null;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`/api${path}`, { ...options, headers });

  if (!res.ok) {
    const body = await res.text();
    let message = `Request failed (${res.status})`;
    try {
      const json = JSON.parse(body);
      message = json.detail || json.message || message;
    } catch {
      // use default
    }
    throw new Error(message);
  }

  return res.json();
}

// Program
export function getActiveProgram(): Promise<{ program: WorkoutProgram | null }> {
  return fetchApi("/workout/program");
}

export function generateProgram(coach: string): Promise<{ program: WorkoutProgram }> {
  return fetchApi("/workout/program/generate", {
    method: "POST",
    body: JSON.stringify({ coach }),
  });
}

// Sessions
export function startWorkout(dayId: string): Promise<StartWorkoutResponse> {
  return fetchApi("/workout/start", {
    method: "POST",
    body: JSON.stringify({ day_id: dayId }),
  });
}

export function getSession(sessionId: string): Promise<WorkoutSessionData> {
  return fetchApi(`/workout/session/${sessionId}`);
}

export function logSet(
  sessionId: string,
  exerciseId: string,
  setNumber: number,
  weightKg: number,
  reps: number
): Promise<LoggedSet> {
  return fetchApi(`/workout/session/${sessionId}/log`, {
    method: "POST",
    body: JSON.stringify({
      exercise_id: exerciseId,
      set_number: setNumber,
      weight_kg: weightKg,
      reps: reps,
    }),
  });
}

export function completeWorkout(sessionId: string): Promise<CompleteWorkoutResponse> {
  return fetchApi(`/workout/session/${sessionId}/complete`, {
    method: "POST",
  });
}

export function getWorkoutHistory(): Promise<WorkoutSessionData[]> {
  return fetchApi("/workout/history");
}

export function getExerciseHistory(exerciseId: string): Promise<ExerciseHistoryEntry[]> {
  return fetchApi(`/workout/exercise/${exerciseId}/history`);
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/types.ts frontend/lib/workout-api.ts
git commit -m "feat(workout): add TypeScript types and API client for workout tracker"
```

---

## Task 5: Sidebar Navigation Update

**Files:**
- Modify: `frontend/components/shared/Sidebar.tsx`

- [ ] **Step 1: Add Program nav item**

In `frontend/components/shared/Sidebar.tsx`, update the imports to add `ClipboardList`:

```typescript
import { LayoutDashboard, Dumbbell, ClipboardList, Settings, LogOut } from "lucide-react";
```

Update the `navItems` array to add Program between Dashboard and Coach:

```typescript
const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/dashboard/program", label: "Program", icon: ClipboardList },
  { href: "/dashboard/ask", label: "Coach", icon: Dumbbell },
  { href: "/dashboard/settings", label: "Settings", icon: Settings },
];
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/shared/Sidebar.tsx
git commit -m "feat(workout): add Program nav item to sidebar"
```

---

## Task 6: Program Overview Page

**Files:**
- Create: `frontend/app/dashboard/program/page.tsx`

- [ ] **Step 1: Create program overview page**

Create `frontend/app/dashboard/program/page.tsx`:

```tsx
"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { ClipboardList, Dumbbell, Play, Loader2 } from "lucide-react";
import { motion } from "framer-motion";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import { getActiveProgram, generateProgram, startWorkout } from "@/lib/workout-api";
import type { WorkoutProgram, ProgramDay } from "@/lib/types";

export default function ProgramPage() {
  const router = useRouter();
  const [program, setProgram] = useState<WorkoutProgram | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [starting, setStarting] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getActiveProgram()
      .then((data) => setProgram(data.program))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const handleGenerate = async () => {
    const coachId = localStorage.getItem("selectedCoach") || "aria";
    setGenerating(true);
    setError("");
    try {
      const data = await generateProgram(coachId);
      setProgram(data.program);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate program");
    } finally {
      setGenerating(false);
    }
  };

  const handleStartWorkout = async (dayId: string) => {
    setStarting(dayId);
    try {
      const data = await startWorkout(dayId);
      router.push(`/dashboard/program/workout/${data.session_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start workout");
      setStarting(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <LoadingSpinner size={48} />
      </div>
    );
  }

  // Empty state
  if (!program) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] text-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <ClipboardList size={48} className="text-[#888] mx-auto mb-4" />
          <h1 className="text-2xl font-heading font-bold text-[#e0e0e0] mb-2">
            No Program Yet
          </h1>
          <p className="text-[#888] mb-6 max-w-md">
            Ask your coach to build a personalized training program based on
            your goals, experience, and schedule.
          </p>
          {error && (
            <p className="text-red-400 text-sm mb-4">{error}</p>
          )}
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="flex items-center gap-2 px-6 py-3 bg-brand text-dark font-semibold rounded-lg hover:bg-brand/90 transition-colors disabled:opacity-50 mx-auto"
          >
            {generating ? (
              <>
                <Loader2 size={18} className="animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Dumbbell size={18} />
                Generate My Program
              </>
            )}
          </button>
        </motion.div>
      </div>
    );
  }

  // Program view
  const days: ProgramDay[] = program.program_data?.days || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-heading font-bold text-[#e0e0e0]">
            {program.name}
          </h1>
          <p className="text-sm text-[#888] mt-1">
            {days.length} training days · Created by your coach
          </p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="px-4 py-2 text-sm border border-border text-[#888] rounded-lg hover:text-[#e0e0e0] hover:border-brand/30 transition-colors disabled:opacity-50"
        >
          {generating ? "Regenerating..." : "Regenerate Program"}
        </button>
      </div>

      {error && (
        <p className="text-red-400 text-sm">{error}</p>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {days.map((day, i) => (
          <motion.div
            key={day.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.08 }}
            className="bg-card border border-border rounded-xl p-5 hover:border-brand/20 transition-colors"
          >
            <div className="flex items-center justify-between mb-3">
              <div>
                <p className="text-xs text-brand uppercase tracking-wider">
                  {day.day_label}
                </p>
                <h2 className="text-lg font-heading font-semibold text-[#e0e0e0]">
                  {day.name}
                </h2>
              </div>
            </div>

            <div className="space-y-1.5 mb-4">
              {day.exercises.map((ex) => (
                <div
                  key={ex.id}
                  className="flex items-center justify-between text-sm"
                >
                  <span className="text-[#ccc] truncate flex-1">
                    {ex.name}
                  </span>
                  <span className="text-[#888] text-xs ml-2 whitespace-nowrap">
                    {ex.sets} sets · {ex.rep_range} reps
                  </span>
                </div>
              ))}
            </div>

            <button
              onClick={() => handleStartWorkout(day.id)}
              disabled={starting === day.id}
              className="w-full flex items-center justify-center gap-2 py-2.5 bg-brand/10 text-brand font-semibold rounded-lg border border-brand/20 hover:bg-brand hover:text-dark transition-all text-sm disabled:opacity-50"
            >
              {starting === day.id ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Play size={16} />
              )}
              {starting === day.id ? "Starting..." : "Start Workout"}
            </button>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/dashboard/program/page.tsx
git commit -m "feat(workout): add program overview page with day cards and generate button"
```

---

## Task 7: Active Workout Page (Compact List + Focused View)

**Files:**
- Create: `frontend/app/dashboard/program/workout/[sessionId]/page.tsx`

- [ ] **Step 1: Create active workout page**

Create directory and file `frontend/app/dashboard/program/workout/[sessionId]/page.tsx`:

```tsx
"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Check,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Minus,
  Plus,
  Trophy,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import {
  getActiveProgram,
  getSession,
  logSet,
  completeWorkout,
} from "@/lib/workout-api";
import type {
  ProgramDay,
  ProgramExercise,
  LoggedSet,
  CompleteWorkoutResponse,
} from "@/lib/types";

// ── Focused Exercise View ───────────────────────────────────────────────

function FocusedExercise({
  exercise,
  exerciseIndex,
  totalExercises,
  sessionId,
  loggedSets,
  lastWeight,
  onSetLogged,
  onBack,
}: {
  exercise: ProgramExercise;
  exerciseIndex: number;
  totalExercises: number;
  sessionId: string;
  loggedSets: LoggedSet[];
  lastWeight: number;
  onSetLogged: (set: LoggedSet) => void;
  onBack: () => void;
}) {
  const completedSets = loggedSets.filter(
    (s) => s.exercise_id === exercise.id
  ).length;
  const nextSetNumber = completedSets + 1;
  const allSetsComplete = completedSets >= exercise.sets;

  const [weight, setWeight] = useState(lastWeight || 20);
  const [reps, setReps] = useState(
    parseInt(exercise.rep_range.split("-")[0]) || 8
  );
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [logging, setLogging] = useState(false);

  const repRange = exercise.rep_range.split("-").map(Number);
  const minReps = repRange[0] || 4;
  const maxReps = repRange[1] || repRange[0] || 12;

  const handleLog = async () => {
    if (allSetsComplete || logging) return;
    setLogging(true);
    try {
      const result = await logSet(
        sessionId,
        exercise.id,
        nextSetNumber,
        weight,
        reps
      );
      onSetLogged(result);
    } catch (err) {
      console.error(err);
    } finally {
      setLogging(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <button
          onClick={onBack}
          className="flex items-center gap-1 text-sm text-[#888] hover:text-[#e0e0e0] transition-colors"
        >
          <ArrowLeft size={16} />
          Back
        </button>
        <div className="flex gap-1">
          {Array.from({ length: totalExercises }).map((_, i) => (
            <div
              key={i}
              className={`w-2 h-2 rounded-full ${
                i < exerciseIndex
                  ? "bg-green-500"
                  : i === exerciseIndex
                  ? "bg-brand"
                  : "bg-[#2a2d37]"
              }`}
            />
          ))}
        </div>
        <span className="text-sm text-[#888]">
          {exerciseIndex + 1} of {totalExercises}
        </span>
      </div>

      {/* Exercise name */}
      <div className="text-center">
        <h2 className="text-2xl font-heading font-bold text-[#e0e0e0]">
          {exercise.name}
        </h2>
        <p className="text-brand text-sm mt-1">
          {exercise.sets} sets · {exercise.rep_range} reps
          {lastWeight > 0 && (
            <span className="text-[#888]"> · Last: {lastWeight}kg</span>
          )}
        </p>
      </div>

      {/* Expandable details */}
      <div className="bg-card border border-border rounded-xl overflow-hidden">
        <button
          onClick={() => setDetailsOpen(!detailsOpen)}
          className="w-full flex items-center justify-between p-4 text-sm text-[#888] hover:text-[#e0e0e0] transition-colors"
        >
          <span>Exercise Details</span>
          {detailsOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
        <AnimatePresence>
          {detailsOpen && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden"
            >
              <div className="px-4 pb-4 space-y-2 border-t border-border pt-3">
                <p className="text-sm text-[#ccc]">{exercise.description}</p>
                <p className="text-sm text-green-400">
                  🔥 {exercise.muscles_targeted.join(", ")}
                </p>
                <p className="text-sm text-red-400">
                  ⚠️ {exercise.muscles_warning}
                </p>
                <p className="text-sm text-[#888]">
                  💡 {exercise.form_cues}
                </p>
                <a
                  href={`https://www.youtube.com/results?search_query=${encodeURIComponent(exercise.youtube_search)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-sm text-brand hover:underline"
                >
                  <ExternalLink size={12} />
                  Watch form video
                </a>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Completed sets */}
      {completedSets > 0 && (
        <div className="space-y-2">
          {loggedSets
            .filter((s) => s.exercise_id === exercise.id)
            .sort((a, b) => a.set_number - b.set_number)
            .map((s) => (
              <div
                key={s.set_number}
                className="flex items-center justify-between bg-card border border-border rounded-lg px-4 py-2 opacity-60"
              >
                <span className="text-sm text-[#888]">
                  Set {s.set_number}
                </span>
                <span className="text-sm text-green-400 font-medium">
                  {s.weight_kg}kg × {s.reps} ✓
                </span>
              </div>
            ))}
        </div>
      )}

      {/* Weight/rep input */}
      {!allSetsComplete && (
        <div className="bg-card border border-brand/30 rounded-xl p-5 space-y-5">
          <div className="text-center text-sm text-brand font-medium">
            Set {nextSetNumber} of {exercise.sets}
          </div>

          {/* Weight */}
          <div className="text-center">
            <div className="text-xs text-[#888] uppercase tracking-wider mb-2">
              Weight
            </div>
            <div className="flex items-center justify-center gap-4">
              <button
                onClick={() => setWeight(Math.max(0, weight - 2.5))}
                className="w-11 h-11 rounded-full bg-dark border border-border flex items-center justify-center text-[#888] hover:text-[#e0e0e0] transition-colors"
              >
                <Minus size={18} />
              </button>
              <div className="text-4xl font-bold text-brand min-w-[100px]">
                {weight}
                <span className="text-base text-[#888] ml-1">kg</span>
              </div>
              <button
                onClick={() => setWeight(weight + 2.5)}
                className="w-11 h-11 rounded-full bg-dark border border-border flex items-center justify-center text-[#888] hover:text-[#e0e0e0] transition-colors"
              >
                <Plus size={18} />
              </button>
            </div>
            <div className="flex justify-center gap-2 mt-3">
              {[-5, -2.5, 0, 2.5, 5].map((delta) => (
                <button
                  key={delta}
                  onClick={() =>
                    delta === 0
                      ? setWeight(lastWeight || weight)
                      : setWeight(Math.max(0, weight + delta))
                  }
                  className={`px-3 py-1 rounded-md text-xs transition-colors ${
                    delta === 0
                      ? "bg-brand text-dark font-semibold"
                      : "bg-dark border border-border text-[#888] hover:text-[#e0e0e0]"
                  }`}
                >
                  {delta === 0 ? "Same" : delta > 0 ? `+${delta}` : delta}
                </button>
              ))}
            </div>
          </div>

          {/* Reps */}
          <div className="text-center">
            <div className="text-xs text-[#888] uppercase tracking-wider mb-2">
              Reps
            </div>
            <div className="flex justify-center gap-2">
              {Array.from(
                { length: maxReps - minReps + 3 },
                (_, i) => minReps - 1 + i
              )
                .filter((r) => r >= 1)
                .map((r) => (
                  <button
                    key={r}
                    onClick={() => setReps(r)}
                    className={`w-10 h-10 rounded-lg text-sm font-medium transition-colors ${
                      reps === r
                        ? "bg-brand/20 border border-brand text-brand"
                        : "bg-dark border border-border text-[#888] hover:text-[#e0e0e0]"
                    }`}
                  >
                    {r}
                  </button>
                ))}
            </div>
          </div>

          {/* Log button */}
          <button
            onClick={handleLog}
            disabled={logging}
            className="w-full py-3.5 bg-brand text-dark font-bold rounded-xl text-lg hover:bg-brand/90 transition-colors disabled:opacity-50"
          >
            {logging ? "Logging..." : "Log Set ✓"}
          </button>
        </div>
      )}

      {/* All sets complete */}
      {allSetsComplete && (
        <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-4 text-center">
          <Check size={24} className="text-green-400 mx-auto mb-1" />
          <p className="text-green-400 font-medium">All sets complete!</p>
          <button
            onClick={onBack}
            className="text-sm text-[#888] hover:text-[#e0e0e0] mt-2 transition-colors"
          >
            Back to exercise list
          </button>
        </div>
      )}
    </div>
  );
}

// ── Debrief Screen ──────────────────────────────────────────────────────

function DebriefScreen({
  debrief,
  durationMin,
  totalSets,
}: {
  debrief: CompleteWorkoutResponse;
  durationMin: number | null;
  totalSets: number;
}) {
  const router = useRouter();

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-lg mx-auto space-y-6 py-8"
    >
      <div className="text-center">
        <Trophy size={48} className="text-brand mx-auto mb-3" />
        <h2 className="text-2xl font-heading font-bold text-[#e0e0e0]">
          Workout Complete!
        </h2>
      </div>

      <div className="flex justify-center gap-6 text-center">
        <div>
          <p className="text-2xl font-bold text-[#e0e0e0]">{totalSets}</p>
          <p className="text-xs text-[#888]">Total Sets</p>
        </div>
        {durationMin && (
          <div>
            <p className="text-2xl font-bold text-[#e0e0e0]">{durationMin}</p>
            <p className="text-xs text-[#888]">Minutes</p>
          </div>
        )}
      </div>

      <div className="bg-card border border-border rounded-xl p-5">
        <p className="text-xs text-brand font-medium mb-2 uppercase tracking-wider">
          Coach Debrief
        </p>
        <p className="text-sm text-[#e0e0e0] leading-relaxed whitespace-pre-wrap">
          {debrief.coach_debrief}
        </p>
      </div>

      <div className="flex gap-3">
        <button
          onClick={() => router.push("/dashboard/program")}
          className="flex-1 py-3 bg-brand text-dark font-semibold rounded-lg hover:bg-brand/90 transition-colors"
        >
          Done
        </button>
        <button
          onClick={() => router.push("/dashboard/ask")}
          className="flex-1 py-3 border border-border text-[#888] rounded-lg hover:text-[#e0e0e0] hover:border-brand/30 transition-colors"
        >
          Chat with Coach
        </button>
      </div>
    </motion.div>
  );
}

// ── Main Workout Page ───────────────────────────────────────────────────

export default function WorkoutPage() {
  const params = useParams();
  const sessionId = params.sessionId as string;
  const router = useRouter();

  const [day, setDay] = useState<ProgramDay | null>(null);
  const [loggedSets, setLoggedSets] = useState<LoggedSet[]>([]);
  const [lastWeights, setLastWeights] = useState<Record<string, number>>({});
  const [focusedExercise, setFocusedExercise] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [completing, setCompleting] = useState(false);
  const [debrief, setDebrief] = useState<CompleteWorkoutResponse | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [programRes, sessionRes] = await Promise.all([
          getActiveProgram(),
          getSession(sessionId),
        ]);

        if (programRes.program) {
          const d = programRes.program.program_data.days.find(
            (d) => d.id === sessionRes.day_id
          );
          setDay(d || null);
        }
        setLoggedSets(sessionRes.sets);

        // Get last weights from the start response stored in URL or reload
        // For simplicity, calculate from session data or default to 0
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [sessionId]);

  const handleSetLogged = (newSet: LoggedSet) => {
    setLoggedSets((prev) => [...prev, newSet]);
    // Update last weights
    setLastWeights((prev) => ({
      ...prev,
      [newSet.exercise_id]: newSet.weight_kg,
    }));
  };

  const handleComplete = async () => {
    setCompleting(true);
    try {
      const result = await completeWorkout(sessionId);
      setDebrief(result);
    } catch (err) {
      console.error(err);
    } finally {
      setCompleting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <LoadingSpinner size={48} />
      </div>
    );
  }

  if (debrief) {
    return (
      <DebriefScreen
        debrief={debrief}
        durationMin={debrief.duration_min}
        totalSets={debrief.total_sets}
      />
    );
  }

  if (!day) {
    return (
      <div className="text-center py-16">
        <p className="text-red-400">Could not load workout data.</p>
        <button
          onClick={() => router.push("/dashboard/program")}
          className="mt-4 text-brand hover:underline text-sm"
        >
          Back to Program
        </button>
      </div>
    );
  }

  // Focused view
  if (focusedExercise !== null) {
    const exercise = day.exercises[focusedExercise];
    return (
      <FocusedExercise
        exercise={exercise}
        exerciseIndex={focusedExercise}
        totalExercises={day.exercises.length}
        sessionId={sessionId}
        loggedSets={loggedSets}
        lastWeight={lastWeights[exercise.id] || 0}
        onSetLogged={handleSetLogged}
        onBack={() => setFocusedExercise(null)}
      />
    );
  }

  // Compact list view
  const exerciseCompletion = day.exercises.map((ex) => {
    const sets = loggedSets.filter((s) => s.exercise_id === ex.id);
    return { exercise: ex, completedSets: sets.length, totalSets: ex.sets };
  });

  const totalCompleted = exerciseCompletion.filter(
    (e) => e.completedSets >= e.totalSets
  ).length;

  const allDone = totalCompleted === day.exercises.length;

  return (
    <div className="space-y-4 max-w-2xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <button
            onClick={() => router.push("/dashboard/program")}
            className="text-xs text-[#888] hover:text-[#e0e0e0] mb-1 flex items-center gap-1 transition-colors"
          >
            <ArrowLeft size={12} /> Program
          </button>
          <p className="text-xs text-brand uppercase tracking-wider">
            {day.day_label}
          </p>
          <h1 className="text-xl font-heading font-bold text-[#e0e0e0]">
            {day.name}
          </h1>
        </div>
        <div className="bg-card border border-border rounded-lg px-3 py-1.5 text-sm text-[#888]">
          {totalCompleted} of {day.exercises.length} done
        </div>
      </div>

      {/* Exercise list */}
      <div className="space-y-2">
        {exerciseCompletion.map(({ exercise, completedSets, totalSets }, i) => {
          const isDone = completedSets >= totalSets;
          const maxWeight = loggedSets
            .filter((s) => s.exercise_id === exercise.id)
            .reduce((max, s) => Math.max(max, s.weight_kg), 0);
          const lastW = lastWeights[exercise.id] || 0;

          return (
            <motion.button
              key={exercise.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              onClick={() => setFocusedExercise(i)}
              className={`w-full text-left bg-card border rounded-xl p-4 transition-all ${
                isDone
                  ? "border-border opacity-60"
                  : "border-brand/30 hover:border-brand/50"
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div
                    className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                      isDone
                        ? "bg-green-500 text-dark"
                        : "bg-brand/20 text-brand"
                    }`}
                  >
                    {isDone ? "✓" : i + 1}
                  </div>
                  <div>
                    <p
                      className={`font-semibold text-sm ${
                        isDone ? "text-[#888]" : "text-[#e0e0e0]"
                      }`}
                    >
                      {exercise.name}
                    </p>
                    <p className="text-xs text-[#888]">
                      {exercise.sets} sets · {exercise.rep_range} reps
                      {lastW > 0 && ` · Last: ${lastW}kg`}
                    </p>
                  </div>
                </div>
                {isDone && maxWeight > 0 && (
                  <span className="text-sm text-green-400 font-medium">
                    {maxWeight}kg ✓
                  </span>
                )}
                {!isDone && completedSets > 0 && (
                  <span className="text-xs text-brand">
                    {completedSets}/{totalSets} sets
                  </span>
                )}
              </div>
            </motion.button>
          );
        })}
      </div>

      {/* Complete workout button */}
      {allDone && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <button
            onClick={handleComplete}
            disabled={completing}
            className="w-full py-4 bg-brand text-dark font-bold rounded-xl text-lg hover:bg-brand/90 transition-colors disabled:opacity-50"
          >
            {completing ? "Getting coach debrief..." : "Complete Workout 🎉"}
          </button>
        </motion.div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/dashboard/program/workout/
git commit -m "feat(workout): add active workout page with compact list, focused view, and debrief"
```

---

## Task 8: Integration Test

**Files:**
- Create: `backend/tests/test_workout_api.py`

- [ ] **Step 1: Write integration test**

Create `backend/tests/test_workout_api.py`:

```python
"""Tests for workout API endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_program_empty(client: AsyncClient):
    resp = await client.get("/api/workout/program")
    assert resp.status_code == 200
    assert resp.json()["program"] is None


@pytest.mark.asyncio
async def test_start_workout_no_program(client: AsyncClient):
    resp = await client.post(
        "/api/workout/start",
        json={"day_id": "mon-upper"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_workout_history_empty(client: AsyncClient):
    resp = await client.get("/api/workout/history")
    assert resp.status_code == 200
    assert resp.json() == []
```

- [ ] **Step 2: Run tests**

Run:
```bash
cd backend && .venv/Scripts/python -m pytest tests/test_workout_api.py -v
```

Expected: 3 tests pass.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_workout_api.py
git commit -m "test(workout): add integration tests for workout API endpoints"
```

---

## Task 9: End-to-End Verification

- [ ] **Step 1: Restart backend**

```bash
taskkill //F //IM python.exe 2>/dev/null
sleep 2
cd backend && .venv/Scripts/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
sleep 6
```

- [ ] **Step 2: Verify program endpoint returns null**

```bash
TOKEN=$(cd backend && .venv/Scripts/python -c "from dotenv import load_dotenv; load_dotenv(); from app.core.security import create_access_token; print(create_access_token('fbc1e205-68f2-4426-9edf-9a8bf3100f0f','test','test'))")
curl -s http://localhost:8000/api/workout/program -H "Authorization: Bearer $TOKEN"
```

Expected: `{"program":null}`

- [ ] **Step 3: Generate a program via API**

```bash
curl -s -X POST http://localhost:8000/api/workout/program/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"coach":"aria"}'
```

Expected: JSON with `program.name`, `program.program_data.days` array containing exercises.

- [ ] **Step 4: Verify program loads on frontend**

Open http://localhost:3000/dashboard/program — should show the generated program with day cards.

- [ ] **Step 5: Commit all remaining changes**

```bash
git add -A
git commit -m "feat(workout): complete training program tracker MVP"
```
