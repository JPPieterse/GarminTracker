# GarminTracker Product Roadmap

> A health platform connecting patients with their doctors through continuous Garmin wearable data and AI-powered insights.

## Business Model

### Cost Structure (per user)
| Component | Per query | Per user/month (est.) |
|-----------|-----------|----------------------|
| Claude SQL generation (Sonnet) | ~$0.01 | — |
| Claude summarization (Sonnet) | ~$0.02 | — |
| Average user (~60 queries/mo) | — | ~$1.80 |
| Hosting + DB + storage | — | ~$0.50 |
| **Total cost per active user** | — | **~$2.30** |

### Pricing Tiers
| Tier | Price | Includes |
|------|-------|----------|
| **Free** | $0/mo | Dashboard, charts, Garmin sync. **5 AI queries/month** |
| **Pro** | $9.99/mo | Unlimited AI queries, voice interface, data export, priority sync |
| **Pro + Doctor** | $14.99/mo | Everything in Pro + doctor sharing portal, medical record uploads |
| **Doctor** | $29.99/mo | Doctor dashboard, up to 50 shared patients, annotations |

### Revenue Math
- Free tier costs ~$0.15/user/month (acquisition funnel)
- Pro at 10% conversion = profitable at ~500 total users
- Doctor plan is high-margin recurring revenue

---

## Architecture Principles

Keep the codebase Claude Code-friendly:
- **Small files** — no file over ~300 lines, split when it grows
- **One concern per file** — routing separate from logic separate from DB
- **Clear naming** — so Claude (and a non-developer owner) can navigate easily
- **Tests alongside features** — every new feature gets a test

### Target Project Structure
```
garmintracker/
├── api/              # FastAPI routes (thin controllers)
│   ├── auth.py
│   ├── health.py
│   ├── doctor.py
│   └── billing.py
├── services/         # Business logic
│   ├── garmin_sync.py
│   ├── llm_analyzer.py
│   ├── sharing.py
│   └── usage.py      # Token tracking & rate limiting
├── models/           # SQLAlchemy models
├── core/             # Config, auth middleware, encryption
├── tests/
└── frontend/         # Next.js app (separate folder)
```

### Tech Stack (Target)
| Component | Choice | Why |
|-----------|--------|-----|
| Backend | FastAPI (Python) | Already built, async, great for APIs |
| Database | PostgreSQL 16 | Multi-user, JSON support, Row-Level Security |
| Auth | Auth0 | Free tier (7,500 users), Google + Apple SSO built-in |
| Frontend | Next.js 14 + TypeScript | React components reusable in mobile app |
| Mobile | Expo (React Native) | Shares logic with Next.js frontend |
| File storage | Cloudflare R2 | Free egress, S3-compatible |
| Hosting | Railway or Render | Simple, cheap ($5-15/mo), built-in Postgres |
| CI/CD | GitHub Actions | Free, already on GitHub |
| Monitoring | Sentry + UptimeRobot | Both have free tiers |
| STT/TTS | Web Speech API | Free, browser-native, good enough to start |

---

## Phase 0: Foundation & Code Quality
*~5 sessions — no feature changes, just production-readiness*

- [ ] Restructure into clean package layout (api/, services/, models/, core/)
- [ ] Add `pyproject.toml` with ruff + mypy config
- [ ] Dockerfile + docker-compose.yml
- [ ] pytest infrastructure with test fixtures (in-memory SQLite)
- [ ] Unit tests: database functions, LLM query builder, result formatter
- [ ] API integration tests (mock Garmin + Anthropic clients)
- [ ] GitHub Actions CI: lint, type-check, test, Docker build
- [ ] Pre-commit hooks (ruff format + lint)
- [ ] Usage tracking table (count AI queries — needed before auth)

## Phase 1: PostgreSQL Migration
*~4 sessions*

- [ ] SQLAlchemy ORM models for all 5 tables + User stub
- [ ] Repository pattern (replace raw sqlite3 calls)
- [ ] Add `user_id` FK to all health data tables (nullable initially)
- [ ] Alembic migrations setup
- [ ] Update docker-compose with PostgreSQL 16
- [ ] Migrate LLM analyzer from SQLite json_extract to PostgreSQL JSONB syntax
- [ ] Data migration script (SQLite → PostgreSQL)
- [ ] Integration tests against real PostgreSQL (testcontainers)

## Phase 2: Auth & Multi-User
*~7 sessions*

- [ ] Auth0 setup: Google + Apple social connections
- [ ] JWT validation middleware (authlib or python-jose)
- [ ] User model: id, email, name, auth_provider, role (PATIENT/DOCTOR)
- [ ] Auto-provisioning on first login
- [ ] Frontend auth flow (Auth0 Universal Login, token in memory)
- [ ] Per-user data isolation (NOT NULL user_id, filtered queries)
- [ ] Per-user Garmin credentials (encrypted in DB, not env vars)
- [ ] Connect/disconnect Garmin UI flow
- [ ] PostgreSQL Row-Level Security for LLM text-to-SQL isolation
- [ ] Auth + isolation tests

## Phase 3: Cloud Deployment
*~5 sessions*

- [ ] Pydantic Settings config (DATABASE_URL, AUTH0_*, ANTHROPIC_API_KEY, etc.)
- [ ] Health check endpoint, structured JSON logging, CORS config
- [ ] Deploy to Railway/Render with managed PostgreSQL
- [ ] Background job for Garmin sync (non-blocking with status polling)
- [ ] Sentry error tracking + uptime monitoring
- [ ] GitHub Actions deploy pipeline (auto-deploy main, preview for PRs)
- [ ] Custom domain + HTTPS

## Phase 4: Doctor Portal & Data Sharing
*~9 sessions*

- [ ] Data model: DoctorPatientLink (status, permissions, expiry)
- [ ] Sharing API: invite, accept, revoke, list
- [ ] Migrate frontend to Next.js 14 + TypeScript + shadcn/ui
- [ ] Recreate patient dashboard in React (feature parity)
- [ ] Doctor dashboard: patient list, shared data view
- [ ] Permission-scoped data access (sleep only, vitals only, etc.)
- [ ] Medical record uploads (Cloudflare R2, encrypted at rest)
- [ ] PDF viewer, doctor annotations, record timeline
- [ ] Audit log: who viewed what, when
- [ ] E2E tests for sharing flow + permission boundaries

## Phase 5: Voice Interface & AI Enhancements
*~5 sessions*

- [ ] Speech-to-text input (Web Speech API, microphone button)
- [ ] Text-to-speech output (Web Speech API, "read aloud" button)
- [ ] Conversation history (chat_messages table, follow-up context)
- [ ] Streaming AI responses (FastAPI StreamingResponse + Anthropic streaming)
- [ ] Doctor-context AI queries (ask about a specific patient's data)

## Phase 6: Security & Compliance (POPIA/GDPR)
*~5 sessions*

- [ ] Data encryption at rest (PostgreSQL TDE or app-level for PII)
- [ ] Cloud KMS for credential encryption (upgrade from Fernet)
- [ ] Comprehensive audit logging (access, sharing, uploads, logins)
- [ ] Data export endpoint (GDPR Article 20 — data portability)
- [ ] Account deletion endpoint (GDPR Article 17 — right to erasure)
- [ ] Security headers (HSTS, CSP, X-Frame-Options)
- [ ] Rate limiting on sensitive endpoints
- [ ] Privacy policy, terms of service, consent tracking

## Phase 7: Mobile App
*~10 sessions*

- [ ] Expo (React Native) app sharing components with Next.js
- [ ] Auth0 native SDK for mobile SSO
- [ ] Push notifications (sync complete, doctor messages)
- [ ] Offline-first with local SQLite cache
- [ ] App Store + Google Play submission

## Phase 8: Growth & Monetization
*~ongoing*

- [ ] Stripe integration for subscription billing
- [ ] Free tier enforcement (5 queries/month limit)
- [ ] Landing page with waitlist
- [ ] Brand identity (name, logo, domain)
- [ ] Analytics (usage tracking, conversion funnel)
- [ ] Referral program (patient invites doctor, doctor invites patients)
