# GarminTracker Full Platform Build — Design Spec

**Date:** 2026-03-25
**Scope:** First iteration of all 8 roadmap phases
**Key decisions:** PostgreSQL from day one, Next.js from day one, monorepo

---

## 1. Architecture

### Monorepo layout

```
GarminTracker/
├── backend/                     # FastAPI (Python 3.12)
│   ├── app/
│   │   ├── api/                 # Route modules (thin controllers)
│   │   │   ├── __init__.py
│   │   │   ├── auth.py          # Auth0 login/callback/logout/me
│   │   │   ├── health.py        # Sync, ask, chart, stats endpoints
│   │   │   ├── doctor.py        # Doctor portal: patients, sharing, annotations
│   │   │   ├── billing.py       # Stripe webhooks, subscription management
│   │   │   └── voice.py         # Streaming AI responses
│   │   ├── services/            # Business logic
│   │   │   ├── garmin_sync.py   # Garmin Connect sync (from existing)
│   │   │   ├── llm_analyzer.py  # Text-to-SQL + summarize (from existing)
│   │   │   ├── sharing.py       # Doctor-patient link management
│   │   │   ├── usage.py         # AI query tracking & rate limiting
│   │   │   ├── storage.py       # Cloudflare R2 file upload/download
│   │   │   └── billing.py       # Stripe subscription logic
│   │   ├── models/              # SQLAlchemy ORM
│   │   │   ├── __init__.py
│   │   │   ├── base.py          # DeclarativeBase + common mixins
│   │   │   ├── user.py          # User model (patient/doctor roles)
│   │   │   ├── health.py        # DailyStats, Activity, Sleep, HeartRate
│   │   │   ├── sharing.py       # DoctorPatientLink, AuditLog
│   │   │   ├── billing.py       # Subscription, UsageRecord
│   │   │   └── chat.py          # ChatMessage (conversation history)
│   │   ├── core/                # Cross-cutting concerns
│   │   │   ├── config.py        # Pydantic Settings (all env vars)
│   │   │   ├── security.py      # Auth0 JWT validation, encryption
│   │   │   ├── database.py      # Async SQLAlchemy engine + session
│   │   │   └── middleware.py     # CORS, security headers, rate limiting
│   │   └── main.py              # FastAPI app factory
│   ├── migrations/              # Alembic
│   │   ├── env.py
│   │   └── versions/
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_health_api.py
│   │   ├── test_auth.py
│   │   ├── test_doctor.py
│   │   ├── test_billing.py
│   │   ├── test_sharing.py
│   │   └── test_models.py
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── alembic.ini
├── frontend/                    # Next.js 14 (TypeScript)
│   ├── app/
│   │   ├── layout.tsx           # Root layout + auth provider
│   │   ├── page.tsx             # Landing/marketing page
│   │   ├── (auth)/
│   │   │   ├── login/page.tsx
│   │   │   └── callback/page.tsx
│   │   ├── dashboard/
│   │   │   ├── layout.tsx       # Authenticated layout
│   │   │   ├── page.tsx         # Main patient dashboard
│   │   │   ├── ask/page.tsx     # AI chat interface
│   │   │   └── settings/page.tsx
│   │   └── doctor/
│   │       ├── layout.tsx
│   │       ├── page.tsx         # Doctor patient list
│   │       └── [patientId]/page.tsx
│   ├── components/
│   │   ├── ui/                  # shadcn/ui components
│   │   ├── charts/              # Chart components (recharts)
│   │   ├── auth/                # Auth provider, protected route
│   │   └── shared/              # Shared between patient & doctor
│   ├── lib/
│   │   ├── api.ts               # Backend API client
│   │   ├── auth.ts              # Auth0 hooks + helpers
│   │   └── types.ts             # Shared TypeScript types
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── next.config.ts
│   └── Dockerfile
├── mobile/                      # Expo (React Native) — scaffold only
│   ├── app/
│   │   ├── _layout.tsx
│   │   ├── index.tsx            # Home/dashboard
│   │   ├── ask.tsx              # AI chat
│   │   └── settings.tsx
│   ├── components/
│   │   ├── charts/
│   │   └── shared/              # Shared with frontend where possible
│   ├── lib/
│   │   ├── api.ts               # Same API client pattern
│   │   └── auth.ts              # Auth0 native SDK
│   ├── app.json
│   └── package.json
├── docker-compose.yml           # PostgreSQL + backend + frontend
├── .env.example                 # All required env vars documented
├── .github/workflows/
│   └── ci.yml                   # Lint + test + type-check + Docker build
└── docs/
```

## 2. Database (PostgreSQL)

### Tables

**users**
- id (UUID, PK), email, name, auth_provider, auth_subject, role (PATIENT/DOCTOR), created_at, updated_at

**daily_stats**
- id (serial PK), user_id (FK users), date, data (JSONB), synced_at

**activities**
- id (bigint PK — Garmin activity ID), user_id (FK users), date, activity_type, name, duration_seconds, distance_meters, calories, avg_hr, max_hr, data (JSONB), synced_at

**sleep**
- id (serial PK), user_id (FK users), date, duration_seconds, deep_seconds, light_seconds, rem_seconds, awake_seconds, data (JSONB), synced_at

**heart_rate**
- id (serial PK), user_id (FK users), date, resting_hr, max_hr, min_hr, data (JSONB), synced_at

**garmin_credentials**
- id (serial PK), user_id (FK users, unique), encrypted_email, encrypted_password, oauth_tokens (JSONB, encrypted), connected_at, last_sync_at

**doctor_patient_links**
- id (UUID PK), doctor_id (FK users), patient_id (FK users), status (PENDING/ACTIVE/REVOKED), permissions (JSONB — {sleep: true, vitals: true, ...}), expires_at, created_at

**medical_records**
- id (UUID PK), user_id (FK users), uploaded_by (FK users), filename, storage_key, content_type, size_bytes, created_at

**doctor_annotations**
- id (UUID PK), doctor_id (FK users), patient_id (FK users), record_id (FK medical_records, nullable), content, created_at

**chat_messages**
- id (UUID PK), user_id (FK users), role (USER/ASSISTANT), content, sql_query, model_used, tokens_used, created_at

**subscriptions**
- id (UUID PK), user_id (FK users, unique), stripe_customer_id, stripe_subscription_id, tier (FREE/PRO/PRO_DOCTOR/DOCTOR), status, current_period_end, created_at

**usage_records**
- id (serial PK), user_id (FK users), action (AI_QUERY/SYNC/UPLOAD), tokens_used, created_at

**audit_log**
- id (serial PK), user_id (FK users), action, target_type, target_id, metadata (JSONB), created_at

### Row-Level Security

RLS policies on all health data tables: patients see only their own data, doctors see linked patients' data filtered by permissions. The LLM text-to-SQL queries run with the user's RLS context so they can never accidentally access other users' data.

## 3. Authentication (Auth0)

- JWT validation via `python-jose` / `authlib`
- Middleware extracts user from `Authorization: Bearer <token>` header
- Auto-provision user record on first successful JWT validation
- Frontend uses Auth0 Universal Login (redirect flow)
- Mobile uses Auth0 native SDK
- Roles: PATIENT (default), DOCTOR (set via invite or manual flag)
- Google + Apple social connections configured (code ready, needs Auth0 account)

## 4. API Design

### Auth endpoints
- `GET /api/auth/login` — redirect to Auth0
- `GET /api/auth/callback` — handle Auth0 callback
- `POST /api/auth/logout` — clear session
- `GET /api/auth/me` — current user info

### Health endpoints (require auth)
- `POST /api/health/sync` — trigger Garmin sync
- `GET /api/health/sync/status` — poll sync progress
- `POST /api/health/ask` — AI question (streaming option)
- `GET /api/health/chart/{metric}` — chart data
- `GET /api/health/stats` — summary stats
- `GET /api/health/export` — GDPR data export (zip)

### Doctor endpoints (require DOCTOR role)
- `GET /api/doctor/patients` — list linked patients
- `POST /api/doctor/invite` — send sharing invite
- `GET /api/doctor/patients/{id}/data` — view patient data (permission-scoped)
- `POST /api/doctor/patients/{id}/annotations` — add annotation
- `GET /api/doctor/patients/{id}/records` — medical records

### Sharing endpoints
- `POST /api/sharing/accept/{link_id}` — accept doctor invite
- `POST /api/sharing/revoke/{link_id}` — revoke sharing
- `GET /api/sharing/links` — list active sharing links

### Billing endpoints
- `POST /api/billing/create-checkout` — Stripe checkout session
- `POST /api/billing/webhook` — Stripe webhook handler
- `GET /api/billing/subscription` — current subscription status
- `POST /api/billing/cancel` — cancel subscription

### Voice endpoint
- `POST /api/health/ask/stream` — SSE streaming AI response

### Admin
- `GET /api/health-check` — health check (no auth)
- `DELETE /api/account` — GDPR right to erasure

## 5. Security & Compliance (POPIA/GDPR)

- All PII encrypted at rest using Fernet (upgradeable to Cloud KMS)
- Garmin credentials encrypted in DB, never stored in plain text
- Security headers: HSTS, CSP, X-Frame-Options, X-Content-Type-Options
- Rate limiting on auth and AI endpoints (slowapi)
- Comprehensive audit logging (all data access, sharing, uploads)
- Data export endpoint (GDPR Article 20)
- Account deletion endpoint (GDPR Article 17 — cascade delete all user data)
- Consent tracking table for privacy policy acceptance
- CORS restricted to known frontend origins

## 6. Billing (Stripe)

- Stripe Checkout for subscription creation
- Webhook handler for subscription lifecycle events
- Free tier: 5 AI queries/month (enforced via usage_records count)
- Pro: unlimited AI queries
- Pro + Doctor: unlimited + doctor sharing
- Doctor: doctor dashboard + up to 50 patients
- Usage tracking on every AI query for rate limiting and billing

## 7. Voice Interface

- Web Speech API for STT (browser-native, free)
- Web Speech API for TTS ("read aloud" button)
- Streaming AI responses via SSE (Server-Sent Events)
- Conversation history stored in chat_messages table
- Follow-up context: last 5 messages sent as context to LLM

## 8. Mobile App (Expo Scaffold)

- Expo Router for navigation
- Auth0 native SDK integration (code ready, needs credentials)
- Same API client pattern as Next.js frontend
- Screens: Dashboard, AI Chat, Settings
- Push notification registration (code ready, needs push service)
- Offline SQLite cache structure defined (not implemented)

## 9. External Service Placeholders

All external services are configured via environment variables with clear documentation in `.env.example`. The code will work with placeholder/empty values where possible and show clear error messages where credentials are required.

```env
# Auth0
AUTH0_DOMAIN=your-tenant.auth0.com
AUTH0_CLIENT_ID=
AUTH0_CLIENT_SECRET=
AUTH0_AUDIENCE=https://api.garmintracker.com

# Stripe
STRIPE_SECRET_KEY=
STRIPE_PUBLISHABLE_KEY=
STRIPE_WEBHOOK_SECRET=

# Cloudflare R2
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=garmintracker-uploads

# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/garmintracker

# Garmin (per-user in production, env var for dev)
GARMIN_EMAIL=
GARMIN_PASSWORD=

# AI
ANTHROPIC_API_KEY=

# Security
ENCRYPTION_KEY=  # Fernet key for PII encryption
```

## 10. What's NOT in this first iteration

- Actual deployment to Railway/Render (code + Dockerfiles ready)
- App Store / Play Store submission (Expo scaffold only)
- Real Auth0 configuration (code ready, needs account)
- Real Stripe billing (code ready, needs account)
- Real Cloudflare R2 uploads (code ready, needs account)
- Production TDE or Cloud KMS (uses Fernet for now)
- Landing page design/copy (basic placeholder only)
- Referral program (tracked in usage, no UI)
