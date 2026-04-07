# ZEV Training Program Tracker — Design Spec

## Overview

A gym-ready workout tracker integrated into ZEV. AI coaches generate structured training programs. Users follow them in the gym, log weights/reps per set, and debrief with their coach after each session. The coach adjusts the program based on feedback.

## Core Principles

- **Coach is the source of truth** — programs are generated and modified by the AI coach, not manually edited by the user
- **Gym-first UI** — big tap targets, minimal typing, pre-filled values, works with sweaty hands
- **Progress is visible** — weight trends (up/down arrows) shown at a glance
- **Conversational adjustments** — after a session, the coach debriefs and the user can request changes through chat

## Data Model

### WorkoutProgram
Stores the coach-generated program structure.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| user_id | UUID | FK → users |
| coach_id | VARCHAR | Which coach created it (max/aria/duke) |
| name | VARCHAR | e.g., "Upper/Lower Power Split" |
| active | BOOLEAN | Only one program active at a time |
| program_data | JSON | Full program structure (see below) |
| created_at | DATETIME | |
| updated_at | DATETIME | |

**program_data JSON structure:**
```json
{
  "days": [
    {
      "id": "mon-upper",
      "name": "Upper Power",
      "day_label": "Monday",
      "exercises": [
        {
          "id": "ex-1",
          "name": "Barbell Bench Press",
          "sets": 4,
          "rep_range": "4-6",
          "description": "Flat bench, full range of motion. Drive through your feet.",
          "muscles_targeted": ["chest", "triceps", "front delts"],
          "muscles_warning": "Don't feel this in your lower back — keep glutes tight",
          "form_cues": "Retract shoulder blades. Touch chest. Explode up.",
          "youtube_search": "barbell bench press form"
        }
      ]
    }
  ]
}
```

### WorkoutSession
One row per gym session (one day of the program).

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| user_id | UUID | FK → users |
| program_id | UUID | FK → workout_programs |
| day_id | VARCHAR | Which day of the program (e.g., "mon-upper") |
| started_at | DATETIME | When the user started |
| finished_at | DATETIME | Nullable — set when workout is completed |
| coach_debrief | TEXT | Coach's post-workout message |
| notes | TEXT | User's optional notes |
| created_at | DATETIME | |

### WorkoutSet
Individual set logs within a session.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| session_id | UUID | FK → workout_sessions |
| exercise_id | VARCHAR | Matches exercise.id in program_data |
| set_number | INT | 1, 2, 3, etc. |
| weight_kg | FLOAT | Weight used |
| reps | INT | Reps completed |
| logged_at | DATETIME | When this set was logged |

## Screens

### 1. Program Overview (new sidebar item: "Program")

Shows the active program with all days listed. Each day shows its exercises in compact form. If no program exists, shows a prompt to ask your coach to create one.

**Empty state:** "No program yet. Ask your coach to build one for you." with a button that opens the coach chat.

**With program:**
- Program name at top
- Cards for each day (Monday Upper, Wednesday Lower, Friday Full Body)
- Each card shows exercise names and prescribed sets/reps
- Tap a day card to start that workout

### 2. Active Workout — Compact List (Layout A)

After tapping a day to start:

- Header: day name, progress indicator ("3 of 6 done")
- Scrollable list of all exercises
- **Completed exercises**: grayed out, green checkmark, weight logged with trend arrow (↑↓→)
- **Active exercise**: highlighted border, shows inline set boxes
- **Upcoming exercises**: dimmed, shows prescribed sets/reps and last weight
- Tap any exercise to open Focused View

**Label format throughout:** `3 sets · 6-8 reps · Last: 50kg`

### 3. Active Workout — Focused View (Layout B)

Tapping an exercise from the compact list opens this:

- Back button to return to list
- Progress dots at top (completed/active/upcoming)
- Large exercise name and prescription
- **Expandable details section** (collapsed by default):
  - Brief description of the movement
  - Muscles targeted (green): "Shoulders, triceps"
  - Warning (red): "Don't feel this in your lower back"
  - Form cues
  - YouTube link for form reference
- **Set logging area**:
  - Pre-filled with last session's weight
  - +/- buttons with ±2.5kg and ±5kg quick-jump chips
  - "Same" chip highlighted by default
  - Rep number selector (tap a number from the prescribed range)
  - Large "Log Set ✓" button
  - After logging, set shows as completed and next set becomes active
- **Next exercise preview** at bottom

### 4. Workout Complete — Coach Debrief

When last set of last exercise is logged:

- Session summary stats (exercises completed, total sets, duration)
- **Coach debrief message** — generated by the selected coach in their personality:
  - References specific exercises and weights from the session
  - Calls out PRs or weight increases
  - Notes any drops in performance
  - Asks how things felt
- User can reply — this feeds into the normal coach chat
- "Done" button returns to Program Overview

## API Endpoints

### Programs
- `GET /api/health/program` — get active program for current user
- `POST /api/health/program/generate` — ask coach to generate a program (sends to LLM)

### Sessions
- `POST /api/health/workout/start` — start a workout session for a given day
- `GET /api/health/workout/{session_id}` — get session with all logged sets
- `POST /api/health/workout/{session_id}/log` — log a single set
- `POST /api/health/workout/{session_id}/complete` — finish workout, trigger coach debrief
- `GET /api/health/workout/history` — past sessions with weights for trend tracking

### Exercise History
- `GET /api/health/exercise/{exercise_id}/history` — weight progression for a specific exercise across sessions

## Program Generation

When the user asks their coach to create a program (either from the empty state button or in chat), the coach uses a structured prompt that outputs valid `program_data` JSON. The backend validates the JSON structure before saving.

The generation prompt includes:
- The user's profile context (goals, training history, injuries)
- The coach's personality
- A JSON schema to follow
- Instruction to include description, muscle targets, warnings, and form cues for every exercise

## Coach Debrief Generation

When a workout is completed, the backend:
1. Loads the session's logged sets
2. Loads the previous session for the same day (for comparison)
3. Sends both to the coach LLM with instructions to debrief
4. Saves the debrief text to the session
5. Returns it to the frontend

The debrief prompt includes the coach's personality, so Max will push harder, Aria will ask about feelings, Duke will focus on running-related benefits.

## Weight Progression Tracking

For each exercise, the system tracks:
- **Last session weight**: pre-filled in the logging UI
- **Trend arrow**: comparing current session to previous (↑ went up, ↓ went down, → same)
- **History**: available via exercise history endpoint for charts later

## Frontend Navigation

Add "Program" to the sidebar between "Dashboard" and "Coach":
- Dashboard
- **Program** (new — clipboard/dumbbell icon)
- Coach
- Settings

## Tech Notes

- All models use the existing `Base`, `UUIDMixin`, `TimestampMixin` from `app.models.base`
- `program_data` uses `JSON` column type (same as other models, SQLite compatible)
- Program generation and debrief use the existing `anthropic` client and coach system
- Frontend uses existing Framer Motion, Recharts, and Tailwind setup
- No new dependencies required
