# Meal Photo Analysis & Always-On Coach Data Context

**Date:** 2026-04-08
**Status:** Approved

## Overview

Three interconnected changes to the ZEV coach system:

1. **Always-on health data context** — The coach always has recent health data in its system prompt, removing the need for users to explicitly request data lookups.
2. **Meal photo analysis** — Users attach a photo of a meal in the chat, the coach analyzes it using Claude's vision, estimates macros, and logs structured nutrition data.
3. **Knowledge module for nutrition estimation** — Domain knowledge for visual portion estimation and food identification.

## Problem Statement

- The coach currently has no health data in CHAT mode. It deflects with "ask me specifically" instead of proactively referencing the user's data.
- When the coach promises to analyze data, the message routes to CHAT (not DATA), so it hallucinates analysis it never performed.
- There is no way to log nutrition data. The Garmin API has nutrition endpoints but they're not integrated, and there's no photo-based meal tracking.
- The coach is not timezone-aware. The server runs in Eastern time but the user is in South Africa.

## Section 1: Always-On Health Data Context

### Recent Data Snapshot

New helper function `_build_recent_snapshot(db, user_id, timezone)` in `llm_analyzer.py`:

- Queries the most recent date that has data, then pulls back up to 14 days (or fewer if less data exists)
- Covers all tables: daily_stats, sleep_records, heart_rate_records, hrv_records, training_readiness_records, body_composition_records, stress_detail_records, performance_metrics, activities, meal_logs
- Returns a compact text summary injected into the coach system prompt for EVERY interaction (both CHAT and DATA routes)
- Includes gap awareness: "Last data: 2026-03-25 (14 days ago)" so the coach can naturally welcome returning users

**Snapshot format example:**
```
## Recent Health Data
Last sync: 2026-04-08 (today)

### 2026-04-08
- Steps: 8,420 | Calories: 2,150 | Stress: 34 | Body Battery: 78
- Sleep: 7.2h (deep 1.4h, REM 1.8h) | Sleep HR: 52
- Resting HR: 58 | HRV: 45 (BALANCED, baseline 44-57)
- Training Readiness: 72 (MODERATE) | Status: PRODUCTIVE
- Activities: Running 5.2km (32min, avg HR 148)
- Meals: Breakfast 450cal (35g P), Lunch 650cal (42g P) — total so far: 1,100cal, 77g protein

### 2026-04-07
- Steps: 11,200 | Calories: 2,580 | Stress: 28 | Body Battery: 82
- Sleep: 7.8h (deep 1.6h, REM 2.0h) | Sleep HR: 50
...
```

### Onboarding Data Context

The existing `_build_data_summary()` in `health.py` already loads broad data for onboarding. Extend it to include the new extended metrics (HRV, training readiness, stress, body composition, performance metrics) so the onboarding coach has the full picture.

### Timezone Awareness

- Add `timezone` field (string, e.g. `"Africa/Johannesburg"`) to the `UserProfile` model
- Capture during onboarding — the coach asks the user's timezone as part of the initial conversation
- Inject into the coach system prompt: `"The user's current local time is 13:37 SAST (Africa/Johannesburg). Today's date in the user's timezone is 2026-04-08."`
- Used for: correct greetings, meal type inference (breakfast/lunch/dinner based on local time), interpreting "yesterday"/"this morning"

### Prompt Changes

- **Remove** from `CHAT_SYSTEM_PROMPT`: "If the user asks something that would need their actual tracked data (steps, sleep, HR), let them know you can look that up if they ask specifically"
- **Add** to `CHAT_SYSTEM_PROMPT`: "You have access to the user's recent health data below. Reference it naturally in conversation. For historical queries beyond what's shown, generate a data lookup."

## Section 2: Meal Photo Analysis

### Endpoint

`POST /api/health/meal/analyze`
- **Auth:** Required (Bearer token)
- **Content-Type:** `multipart/form-data`
- **Fields:**
  - `image` (file, required) — the meal photo
  - `message` (string, optional) — user's text alongside the photo
  - `coach` (string, optional) — coach ID (defaults to user's selected coach)
- **Response:** Same shape as `/health/ask` — `{answer, results, model, count}`
- **Image handling:** Read into memory as base64, passed to Claude, then discarded. Never stored to disk or R2.

### Data Model

New `MealLog` table:

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | Primary key |
| user_id | UUID | FK to users |
| date | DATE | In user's local timezone |
| time | TIME | In user's local timezone |
| meal_type | ENUM | BREAKFAST, LUNCH, DINNER, SNACK — auto-inferred from local time |
| calories | INT | Estimated total |
| protein_g | FLOAT | |
| carbs_g | FLOAT | |
| fat_g | FLOAT | |
| fiber_g | FLOAT | Optional |
| sodium_mg | FLOAT | Optional |
| ingredients | TEXT | Human-readable: "grilled chicken breast ~180g, brown rice ~1 cup" |
| confidence | ENUM | HIGH, MEDIUM, LOW |
| notes | TEXT | Coach clarifications or user context |
| hydration_ml | INT | Optional — from conversational estimates |
| created_at | DATETIME | |
| updated_at | DATETIME | |

### LLM Flow

1. User attaches photo (+ optional message like "post-workout meal")
2. Backend builds Claude message with:
   - Image as an `image` content block (base64)
   - User's text message (if any)
   - Coach persona system addendum
   - Nutrition knowledge module (auto-injected)
   - Meal photo analysis knowledge module (auto-injected)
   - User profile context (dietary goals, restrictions from onboarding)
   - Today's running meal totals from `meal_logs` ("You've had 1,400 cal today so far across breakfast and lunch")
   - Recent health data snapshot
3. Claude responds conversationally as the coach AND includes a `[MEAL_LOG]` tag:
   ```
   [MEAL_LOG]
   {"calories": 650, "protein_g": 42, "carbs_g": 55, "fat_g": 22, "fiber_g": 8, "sodium_mg": 480, "ingredients": "grilled chicken breast ~180g, brown rice ~1 cup, steamed broccoli ~1 cup, olive oil drizzle", "confidence": "HIGH"}
   ```
4. Backend extracts `[MEAL_LOG]` JSON via regex (same pattern as `[PROGRAM_UPDATE]`), saves `MealLog` record
5. Strips the tag from the response, returns conversational text to frontend
6. Both the user message and coach response are saved to `ChatMessage` history

### Confidence & Follow-Up

- **HIGH:** Clear photo, identifiable ingredients, standard portions
- **MEDIUM:** Some ambiguity in portions or preparation method — coach mentions this naturally
- **LOW:** Blurry photo, complex mixed dish, can't identify ingredients — coach gives rough estimate and asks clarifying questions
- If the user replies with clarifications, the coach sends an updated `[MEAL_LOG]` that creates a new record (the previous LOW-confidence one can be replaced by matching user_id + date + time window)

### Honesty Guardrail

The meal analysis system prompt includes: "You are providing practical estimates for everyday health coaching, not clinical measurements. If a meal is complex, portions are hard to judge from the photo, or you're genuinely uncertain, say so honestly. Frame all estimates as approximations. This is coaching guidance for general wellness — not competition prep or medical dietary management."

### Hydration

When the coach is in meal-tracking context, it can naturally ask "How much water have you had today?" The user's conversational answer (e.g., "about 3 glasses") gets estimated in ml and stored in the `hydration_ml` field of the most recent meal log for that day. This is a rough estimate, not precise tracking.

## Section 3: Knowledge Module

### New File: `backend/knowledge/meal-photo-analysis.md`

Content covers:
- **Visual portion estimation:** palm = ~1 protein serving (~100-120g), fist = ~1 cup carbs, thumb tip = ~1 tsp fat, cupped hand = ~1/2 cup
- **Common food caloric density:** cooked rice ~200cal/cup, chicken breast ~165cal/100g, salmon ~208cal/100g, pasta ~220cal/cup cooked, bread ~80cal/slice
- **Cooking method adjustments:** fried vs grilled adds ~30-50% calories from oil absorption, sauces add 50-150cal per serving
- **Plating cues:** standard dinner plate ~10-11 inches, food-to-plate ratio indicates portion size, sauce pooling indicates extra calories
- **Common estimation pitfalls:** hidden oils, creamy dressings (150-200cal/2tbsp), sugar in sauces, nuts/seeds caloric density, portion underestimation bias
- **Regional food awareness:** South African dishes with typical macro profiles — bunny chow (~600-900cal depending on size), biltong (~250cal/100g, 55g protein), boerewors (~280cal/100g), pap with sauce (~300-400cal/serving), vetkoek (~350cal each), chakalaka (~80cal/serving)

**Keyword triggers added to `knowledge.py`:** "meal", "food", "ate", "eating", "photo", "picture", "breakfast", "lunch", "dinner", "snack", "calories", "macros", "protein", "nutrition"

### Updated `DB_SCHEMA`

Add `meal_logs` table description to the schema string in `llm_analyzer.py` so the DATA route can generate SQL queries against meal data:
```
- meal_logs: id (UUID), user_id (UUID), date (DATE), time (TIME), meal_type (VARCHAR),
  calories (INT), protein_g (FLOAT), carbs_g (FLOAT), fat_g (FLOAT),
  fiber_g (FLOAT), sodium_mg (FLOAT), ingredients (TEXT), confidence (VARCHAR),
  notes (TEXT), hydration_ml (INT)
```

## Section 4: Frontend — WhatsApp-Style Attachment UX

### Chat Input Bar

Modify the existing input bar in `app/dashboard/ask/page.tsx`:

- **Attach button** (paperclip icon) added to the left of the text input
- On click, shows a small popover with two options:
  - **Gallery** (image icon) — triggers `<input type="file" accept="image/*">`
  - **Camera** (camera icon) — triggers `<input type="file" accept="image/*" capture="environment">`
- When a photo is selected, a small thumbnail preview appears above the input bar with an X button to dismiss
- User can type an optional message alongside the photo
- Send button posts to `/api/health/meal/analyze` when an image is attached, or to `/health/ask` when text-only
- While processing, show the coach's typing indicator (existing pattern)

### User's Chat Bubble

When the user sends a meal photo, their chat bubble displays:
- **"Sent a photo"** (if no text message)
- **"Sent a photo: post-workout meal"** (if text was included)

No thumbnail or image rendering. The photo is discarded on the backend so there's nothing to show in history.

### Chat Message Persistence

The user's message is saved to `ChatMessage` as "Sent a photo" or "Sent a photo: {message}". The coach's response is saved normally. When scrolling back through history, the conversation reads naturally without needing the original image.

### New API Client Method

In `lib/api.ts`:
```typescript
export function analyzeMeal(image: File, message?: string, coach?: string): Promise<AskResponse> {
  // Posts multipart/form-data instead of JSON
}
```

## Files Changed

### Backend (new)
- `app/models/meal.py` — MealLog model
- `backend/knowledge/meal-photo-analysis.md` — visual estimation knowledge module

### Backend (modified)
- `app/models/user.py` — add `timezone` field to UserProfile
- `app/models/__init__.py` — import MealLog
- `app/services/llm_analyzer.py` — add `_build_recent_snapshot()`, update CHAT_SYSTEM_PROMPT, add `[MEAL_LOG]` extraction, update DB_SCHEMA, add timezone to prompts
- `app/services/knowledge.py` — add meal-related keywords
- `app/api/health.py` — add `POST /health/meal/analyze` endpoint, extend onboarding data summary
- `app/main.py` — ensure meal model tables are created on startup

### Frontend (modified)
- `app/dashboard/ask/page.tsx` — attach button, popover, thumbnail preview, "Sent a photo" bubbles
- `lib/api.ts` — add `analyzeMeal()` method

### Database
- New table: `meal_logs`
- New column: `user_profiles.timezone`
