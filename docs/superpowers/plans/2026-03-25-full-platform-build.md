# GarminTracker Full Platform Build — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a first iteration of all 8 roadmap phases — PostgreSQL, Auth0, Next.js frontend, doctor portal, voice, security/compliance, mobile scaffold, and billing.

**Architecture:** Monorepo with `backend/` (FastAPI + SQLAlchemy + Alembic), `frontend/` (Next.js 14 + TypeScript + shadcn/ui), and `mobile/` (Expo scaffold). PostgreSQL and Next.js from day one. External services (Auth0, Stripe, R2) fully coded with env-var placeholders.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic, PostgreSQL 16, Next.js 14, TypeScript, Tailwind CSS, shadcn/ui, Expo (React Native), Stripe SDK, Auth0

---

## Task Group A: Backend Restructure + PostgreSQL (Phase 0 + 1)

### Task A1: Scaffold backend package layout

**Files:**
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/core/database.py`
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/base.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/pyproject.toml`
- Create: `backend/alembic.ini`
- Create: `backend/migrations/env.py`
- Create: `backend/migrations/versions/.gitkeep`

- [ ] **Step 1: Create backend/pyproject.toml**

```toml
[project]
name = "garmintracker-backend"
version = "0.1.0"
description = "GarminTracker API backend"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.30",
    "alembic>=1.14",
    "pydantic-settings>=2.7",
    "python-jose[cryptography]>=3.3",
    "passlib[bcrypt]>=1.7",
    "cryptography>=44.0",
    "garminconnect>=0.2.25",
    "anthropic>=0.43",
    "httpx>=0.27",
    "python-dotenv>=1.0",
    "python-multipart>=0.0.18",
    "slowapi>=0.1.9",
    "boto3>=1.35",
    "stripe>=11.0",
    "sse-starlette>=2.0",
    "structlog>=24.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "httpx>=0.27",
    "ruff>=0.8",
    "mypy>=1.13",
    "testcontainers[postgres]>=4.0",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["app*"]

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "W", "F", "I", "UP", "B", "SIM"]

[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = false

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 2: Create backend/app/core/config.py — Pydantic Settings**

```python
"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All configuration loaded from environment variables."""

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/garmintracker"

    # Auth0
    auth0_domain: str = ""
    auth0_client_id: str = ""
    auth0_client_secret: str = ""
    auth0_audience: str = "https://api.garmintracker.com"

    # Stripe
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""

    # Cloudflare R2
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = "garmintracker-uploads"
    r2_endpoint_url: str = ""

    # Garmin (dev only — per-user in production)
    garmin_email: str = ""
    garmin_password: str = ""

    # AI
    anthropic_api_key: str = ""
    default_model: str = "phi4-mini"

    # Security
    encryption_key: str = ""  # Fernet key for PII encryption
    cors_origins: list[str] = ["http://localhost:3000"]

    # App
    debug: bool = False
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
```

- [ ] **Step 3: Create backend/app/core/database.py — async SQLAlchemy engine**

```python
"""Async database engine and session factory."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields an async database session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

- [ ] **Step 4: Create backend/app/models/base.py — SQLAlchemy base + mixins**

```python
"""SQLAlchemy declarative base and common mixins."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    """Adds created_at and updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class UUIDMixin:
    """Adds a UUID primary key."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
```

- [ ] **Step 5: Create backend/app/__init__.py and backend/app/core/__init__.py and backend/app/models/__init__.py and backend/app/api/__init__.py (empty files)**

- [ ] **Step 6: Create backend/app/main.py — FastAPI app factory**

```python
"""FastAPI application factory."""

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

logger = structlog.get_logger()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="GarminTracker API",
        version="0.1.0",
        docs_url="/api/docs" if settings.debug else None,
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health-check")
    async def health_check():
        return {"status": "ok", "version": "0.1.0"}

    # Import and include routers (added as we build them)
    from app.api.health import router as health_router
    app.include_router(health_router, prefix="/api/health", tags=["health"])

    from app.api.auth import router as auth_router
    app.include_router(auth_router, prefix="/api/auth", tags=["auth"])

    from app.api.doctor import router as doctor_router
    app.include_router(doctor_router, prefix="/api/doctor", tags=["doctor"])

    from app.api.billing import router as billing_router
    app.include_router(billing_router, prefix="/api/billing", tags=["billing"])

    return app


app = create_app()
```

- [ ] **Step 7: Set up Alembic**

Create `backend/alembic.ini`:
```ini
[alembic]
script_location = migrations
sqlalchemy.url = postgresql+asyncpg://postgres:postgres@localhost:5432/garmintracker

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

Create `backend/migrations/env.py`:
```python
"""Alembic migration environment."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings
from app.models.base import Base

# Import all models so Alembic sees them
from app.models import health, user, sharing, billing, chat  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

Create `backend/migrations/versions/.gitkeep` (empty file).

- [ ] **Step 8: Commit**

```bash
git add backend/
git commit -m "feat: scaffold backend package with FastAPI, SQLAlchemy, Alembic, Pydantic Settings"
```

---

### Task A2: ORM models for all tables

**Files:**
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/health.py`
- Create: `backend/app/models/sharing.py`
- Create: `backend/app/models/billing.py`
- Create: `backend/app/models/chat.py`

- [ ] **Step 1: Create backend/app/models/user.py**

```python
"""User model with role-based access."""

import enum

from sqlalchemy import Enum, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class UserRole(str, enum.Enum):
    PATIENT = "patient"
    DOCTOR = "doctor"


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    auth_provider: Mapped[str] = mapped_column(String(50), nullable=False, default="auth0")
    auth_subject: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole), nullable=False, default=UserRole.PATIENT
    )

    # Relationships
    daily_stats = relationship("DailyStat", back_populates="user", cascade="all, delete-orphan")
    activities = relationship("Activity", back_populates="user", cascade="all, delete-orphan")
    sleep_records = relationship("SleepRecord", back_populates="user", cascade="all, delete-orphan")
    heart_rate_records = relationship("HeartRateRecord", back_populates="user", cascade="all, delete-orphan")
    garmin_credential = relationship("GarminCredential", back_populates="user", uselist=False, cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="user", cascade="all, delete-orphan")
    subscription = relationship("Subscription", back_populates="user", uselist=False, cascade="all, delete-orphan")
    usage_records = relationship("UsageRecord", back_populates="user", cascade="all, delete-orphan")


class GarminCredential(TimestampMixin, Base):
    __tablename__ = "garmin_credentials"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped["uuid.UUID"] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    encrypted_email: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_password: Mapped[str] = mapped_column(Text, nullable=False)
    oauth_tokens: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    last_sync_at: Mapped["datetime | None"] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="garmin_credential")
```

- [ ] **Step 2: Create backend/app/models/health.py**

```python
"""Health data models — daily stats, activities, sleep, heart rate."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class DailyStat(Base):
    __tablename__ = "daily_stats"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user = relationship("User", back_populates="daily_stats")

    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_daily_stats_user_date"),)


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Garmin activity ID
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    activity_type: Mapped[str | None] = mapped_column(String(50))
    name: Mapped[str | None] = mapped_column(String(255))
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    distance_meters: Mapped[float | None] = mapped_column(Float)
    calories: Mapped[float | None] = mapped_column(Float)
    avg_hr: Mapped[float | None] = mapped_column(Float)
    max_hr: Mapped[float | None] = mapped_column(Float)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user = relationship("User", back_populates="activities")


class SleepRecord(Base):
    __tablename__ = "sleep"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    deep_seconds: Mapped[float | None] = mapped_column(Float)
    light_seconds: Mapped[float | None] = mapped_column(Float)
    rem_seconds: Mapped[float | None] = mapped_column(Float)
    awake_seconds: Mapped[float | None] = mapped_column(Float)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user = relationship("User", back_populates="sleep_records")

    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_sleep_user_date"),)


class HeartRateRecord(Base):
    __tablename__ = "heart_rate"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    resting_hr: Mapped[int | None] = mapped_column(Integer)
    max_hr: Mapped[int | None] = mapped_column(Integer)
    min_hr: Mapped[int | None] = mapped_column(Integer)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user = relationship("User", back_populates="heart_rate_records")

    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_heart_rate_user_date"),)


class SyncLog(Base):
    __tablename__ = "sync_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
```

- [ ] **Step 3: Create backend/app/models/sharing.py**

```python
"""Doctor-patient sharing models."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class LinkStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    REVOKED = "revoked"


class DoctorPatientLink(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "doctor_patient_links"

    doctor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status: Mapped[LinkStatus] = mapped_column(Enum(LinkStatus), nullable=False, default=LinkStatus.PENDING)
    permissions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MedicalRecord(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "medical_records"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(nullable=False)


class DoctorAnnotation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "doctor_annotations"

    doctor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    record_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("medical_records.id"))
    content: Mapped[str] = mapped_column(Text, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(50))
    target_id: Mapped[str | None] = mapped_column(String(255))
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
```

- [ ] **Step 4: Create backend/app/models/billing.py**

```python
"""Billing and usage tracking models."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class SubscriptionTier(str, enum.Enum):
    FREE = "free"
    PRO = "pro"
    PRO_DOCTOR = "pro_doctor"
    DOCTOR = "doctor"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    TRIALING = "trialing"


class Subscription(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255))
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255))
    tier: Mapped[SubscriptionTier] = mapped_column(Enum(SubscriptionTier), nullable=False, default=SubscriptionTier.FREE)
    status: Mapped[SubscriptionStatus] = mapped_column(Enum(SubscriptionStatus), nullable=False, default=SubscriptionStatus.ACTIVE)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user = relationship("User", back_populates="subscription")


class UsageAction(str, enum.Enum):
    AI_QUERY = "ai_query"
    SYNC = "sync"
    UPLOAD = "upload"


class UsageRecord(Base):
    __tablename__ = "usage_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    action: Mapped[UsageAction] = mapped_column(Enum(UsageAction), nullable=False)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="usage_records")
```

- [ ] **Step 5: Create backend/app/models/chat.py**

```python
"""Chat message model for conversation history."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(UUIDMixin, Base):
    __tablename__ = "chat_messages"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sql_query: Mapped[str | None] = mapped_column(Text)
    model_used: Mapped[str | None] = mapped_column(String(100))
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="chat_messages")
```

- [ ] **Step 6: Update backend/app/models/__init__.py to import all models**

```python
"""Import all models so Alembic can discover them."""

from app.models.base import Base
from app.models.billing import Subscription, UsageRecord
from app.models.chat import ChatMessage
from app.models.health import Activity, DailyStat, HeartRateRecord, SleepRecord, SyncLog
from app.models.sharing import AuditLog, DoctorAnnotation, DoctorPatientLink, MedicalRecord
from app.models.user import GarminCredential, User

__all__ = [
    "Base", "User", "GarminCredential",
    "DailyStat", "Activity", "SleepRecord", "HeartRateRecord", "SyncLog",
    "DoctorPatientLink", "MedicalRecord", "DoctorAnnotation", "AuditLog",
    "Subscription", "UsageRecord", "ChatMessage",
]
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/
git commit -m "feat: add all SQLAlchemy ORM models (user, health, sharing, billing, chat)"
```

---

### Task A3: Core security module (Auth0 JWT + encryption)

**Files:**
- Create: `backend/app/core/security.py`

- [ ] **Step 1: Create backend/app/core/security.py**

```python
"""Authentication (Auth0 JWT) and encryption utilities."""

import uuid
from typing import Annotated

import httpx
from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User, UserRole

security_scheme = HTTPBearer(auto_error=False)

# Cache Auth0 JWKS
_jwks_cache: dict | None = None


async def _get_jwks() -> dict:
    """Fetch Auth0 JWKS (cached)."""
    global _jwks_cache
    if _jwks_cache is None:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"https://{settings.auth0_domain}/.well-known/jwks.json")
            resp.raise_for_status()
            _jwks_cache = resp.json()
    return _jwks_cache


async def _verify_token(token: str) -> dict:
    """Verify an Auth0 JWT and return the payload."""
    jwks = await _get_jwks()
    unverified_header = jwt.get_unverified_header(token)

    rsa_key = {}
    for key in jwks.get("keys", []):
        if key["kid"] == unverified_header.get("kid"):
            rsa_key = {
                "kty": key["kty"],
                "kid": key["kid"],
                "use": key["use"],
                "n": key["n"],
                "e": key["e"],
            }
            break

    if not rsa_key:
        raise HTTPException(status_code=401, detail="Unable to find signing key")

    payload = jwt.decode(
        token,
        rsa_key,
        algorithms=["RS256"],
        audience=settings.auth0_audience,
        issuer=f"https://{settings.auth0_domain}/",
    )
    return payload


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Extract and validate user from JWT. Auto-provisions on first login."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not settings.auth0_domain:
        # Dev mode: create/return a dev user when Auth0 is not configured
        return await _get_or_create_dev_user(db)

    try:
        payload = await _verify_token(credentials.credentials)
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

    sub = payload.get("sub", "")
    email = payload.get("email", payload.get(f"https://{settings.auth0_domain}/email", ""))
    name = payload.get("name", "")

    # Auto-provision user on first login
    result = await db.execute(select(User).where(User.auth_subject == sub))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            email=email,
            name=name,
            auth_provider="auth0",
            auth_subject=sub,
            role=UserRole.PATIENT,
        )
        db.add(user)
        await db.flush()

    return user


async def _get_or_create_dev_user(db: AsyncSession) -> User:
    """In dev mode (no Auth0), use a fixed dev user."""
    dev_sub = "dev|local"
    result = await db.execute(select(User).where(User.auth_subject == dev_sub))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            email="dev@localhost",
            name="Dev User",
            auth_provider="dev",
            auth_subject=dev_sub,
            role=UserRole.PATIENT,
        )
        db.add(user)
        await db.flush()
    return user


def require_role(required_role: UserRole):
    """Dependency that checks the user has a specific role."""
    async def check(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role != required_role:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return check


# --- Encryption ---

def get_fernet() -> Fernet:
    """Get Fernet instance for PII encryption."""
    key = settings.encryption_key
    if not key:
        key = Fernet.generate_key().decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_value(value: str) -> str:
    """Encrypt a string value."""
    return get_fernet().encrypt(value.encode()).decode()


def decrypt_value(encrypted: str) -> str:
    """Decrypt an encrypted string value."""
    return get_fernet().decrypt(encrypted.encode()).decode()
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/core/security.py
git commit -m "feat: add Auth0 JWT validation, auto-provisioning, dev mode, Fernet encryption"
```

---

### Task A4: Backend services layer

**Files:**
- Create: `backend/app/services/garmin_sync.py`
- Create: `backend/app/services/llm_analyzer.py`
- Create: `backend/app/services/usage.py`
- Create: `backend/app/services/sharing.py`
- Create: `backend/app/services/storage.py`
- Create: `backend/app/services/billing.py`
- Create: `backend/app/services/__init__.py`

- [ ] **Step 1: Create backend/app/services/garmin_sync.py** (ported from existing, now multi-user + async)

```python
"""Garmin Connect data sync service."""

import logging
import time
import uuid
from datetime import date, datetime, timedelta, timezone

from garminconnect import Garmin
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_value
from app.models.health import Activity, DailyStat, HeartRateRecord, SleepRecord, SyncLog
from app.models.user import GarminCredential

logger = logging.getLogger(__name__)


def _get_client(email: str, password: str, oauth_tokens: dict | None = None) -> Garmin:
    """Create an authenticated Garmin client."""
    client = Garmin(email, password)
    try:
        client.login()
    except Exception:
        client.login()
    return client


async def sync_user_data(
    db: AsyncSession, user_id: uuid.UUID, days: int = 7
) -> list[dict]:
    """Sync Garmin data for a user. Returns list of per-day results."""
    # Get credentials
    result = await db.execute(
        select(GarminCredential).where(GarminCredential.user_id == user_id)
    )
    cred = result.scalar_one_or_none()
    if cred is None:
        raise ValueError("No Garmin credentials configured. Connect your Garmin account first.")

    email = decrypt_value(cred.encrypted_email)
    password = decrypt_value(cred.encrypted_password)

    # Create sync log
    sync_log = SyncLog(
        user_id=user_id,
        started_at=datetime.now(timezone.utc),
        status="running",
    )
    db.add(sync_log)
    await db.flush()

    try:
        client = _get_client(email, password, cred.oauth_tokens)
        end = date.today()
        start = end - timedelta(days=days - 1)
        results = []

        current = start
        while current <= end:
            day_result = await _sync_date(db, client, user_id, current)
            results.append({"date": current.isoformat(), **day_result})
            current += timedelta(days=1)
            time.sleep(1)

        sync_log.status = "completed"
        sync_log.finished_at = datetime.now(timezone.utc)
        sync_log.message = f"Synced {len(results)} days"

        # Update last_sync_at
        cred.last_sync_at = datetime.now(timezone.utc)

        return results

    except Exception as e:
        sync_log.status = "failed"
        sync_log.finished_at = datetime.now(timezone.utc)
        sync_log.message = str(e)
        raise


async def _sync_date(
    db: AsyncSession, client: Garmin, user_id: uuid.UUID, dt: date
) -> dict:
    """Sync all data types for a single date."""
    date_str = dt.isoformat()
    now = datetime.now(timezone.utc)
    synced = {}

    # Daily stats
    try:
        stats = client.get_stats(date_str)
        if stats:
            daily = DailyStat(user_id=user_id, date=date_str, data=stats, synced_at=now)
            await db.merge(daily)
            synced["daily_stats"] = True
    except Exception as e:
        logger.warning(f"Daily stats failed for {date_str}: {e}")
        synced["daily_stats"] = str(e)

    time.sleep(0.5)

    # Activities
    try:
        activities = client.get_activities_by_date(date_str, date_str)
        for act in activities or []:
            activity = Activity(
                id=act.get("activityId"),
                user_id=user_id,
                date=date_str,
                activity_type=act.get("activityType", {}).get("typeKey", "unknown"),
                name=act.get("activityName", ""),
                duration_seconds=act.get("duration"),
                distance_meters=act.get("distance"),
                calories=act.get("calories"),
                avg_hr=act.get("averageHR"),
                max_hr=act.get("maxHR"),
                data=act,
                synced_at=now,
            )
            await db.merge(activity)
        synced["activities"] = len(activities or [])
    except Exception as e:
        logger.warning(f"Activities failed for {date_str}: {e}")
        synced["activities"] = str(e)

    time.sleep(0.5)

    # Sleep
    try:
        sleep = client.get_sleep_data(date_str)
        if sleep and sleep.get("dailySleepDTO"):
            s = sleep["dailySleepDTO"]
            rec = SleepRecord(
                user_id=user_id,
                date=date_str,
                duration_seconds=s.get("sleepTimeInSeconds"),
                deep_seconds=s.get("deepSleepSeconds"),
                light_seconds=s.get("lightSleepSeconds"),
                rem_seconds=s.get("remSleepSeconds"),
                awake_seconds=s.get("awakeSleepSeconds"),
                data=s,
                synced_at=now,
            )
            await db.merge(rec)
            synced["sleep"] = True
    except Exception as e:
        logger.warning(f"Sleep failed for {date_str}: {e}")
        synced["sleep"] = str(e)

    time.sleep(0.5)

    # Heart rate
    try:
        hr = client.get_heart_rates(date_str)
        if hr:
            rec = HeartRateRecord(
                user_id=user_id,
                date=date_str,
                resting_hr=hr.get("restingHeartRate"),
                max_hr=hr.get("maxHeartRate"),
                min_hr=hr.get("minHeartRate"),
                data=hr,
                synced_at=now,
            )
            await db.merge(rec)
            synced["heart_rate"] = True
    except Exception as e:
        logger.warning(f"Heart rate failed for {date_str}: {e}")
        synced["heart_rate"] = str(e)

    return synced
```

- [ ] **Step 2: Create backend/app/services/llm_analyzer.py** (ported from existing, now multi-user + PostgreSQL JSONB)

```python
"""LLM-powered health data analysis using text-to-SQL."""

import json
import logging
import uuid
from datetime import date, datetime, timezone

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.chat import ChatMessage, MessageRole

logger = logging.getLogger(__name__)

MODELS = {
    "phi4-mini": {"name": "Phi-4 Mini (3.8B)", "backend": "ollama", "model_id": "phi4-mini"},
    "qwen2.5-coder:1.5b": {"name": "Qwen 2.5 Coder 1.5B", "backend": "ollama", "model_id": "qwen2.5-coder:1.5b"},
    "qwen2.5-coder:7b": {"name": "Qwen 2.5 Coder 7B", "backend": "ollama", "model_id": "qwen2.5-coder:7b"},
    "gemma2:2b": {"name": "Gemma 2 2B", "backend": "ollama", "model_id": "gemma2:2b"},
    "llama3.2:3b": {"name": "Llama 3.2 3B", "backend": "ollama", "model_id": "llama3.2:3b"},
    "haiku": {"name": "Claude Haiku 4.5", "backend": "anthropic", "model_id": "claude-haiku-4-5-20251001"},
    "sonnet": {"name": "Claude Sonnet 4.6", "backend": "anthropic", "model_id": "claude-sonnet-4-6-20250514"},
}

OLLAMA_BASE = "http://localhost:11434"

SCHEMA_DESCRIPTION = """
You have access to a PostgreSQL database with these tables (filtered to the current user via user_id):

daily_stats: id, user_id, date (TEXT 'YYYY-MM-DD'), data (JSONB)
  JSONB fields: totalSteps, totalDistanceMeters, totalKilocalories, activeKilocalories,
  activeSeconds, sedentarySeconds, floorsAscended, averageStressLevel, maxStressLevel,
  stepsGoal, moderateIntensityMinutes, vigorousIntensityMinutes,
  bodyBatteryHighestValue, bodyBatteryLowestValue, averageSpO2, lowestSpO2

activities: id, user_id, date, activity_type, name, duration_seconds, distance_meters,
  calories, avg_hr, max_hr, data (JSONB)

sleep: id, user_id, date, duration_seconds, deep_seconds, light_seconds, rem_seconds,
  awake_seconds, data (JSONB)

heart_rate: id, user_id, date, resting_hr, max_hr, min_hr, data (JSONB)

NOTES:
- ALWAYS filter by user_id = :user_id parameter. This is mandatory.
- Use data->>'fieldName' or (data->>'fieldName')::numeric for JSONB access.
- Dates are TEXT 'YYYY-MM-DD'. Use CURRENT_DATE for today.
- To convert seconds: column / 3600.0 for hours, column / 60.0 for minutes.
- To convert meters to km: column / 1000.0
"""

SQL_SYSTEM_PROMPT = f"""You are a health data analyst that writes SQL queries.
The user has a Garmin smartwatch and their data is stored in PostgreSQL.

{SCHEMA_DESCRIPTION}

Today's date is {{today}}.

Given the user's question, write a PostgreSQL query to retrieve the relevant data.
Return ONLY a JSON object: {{"sql": "SELECT ...", "explanation": "Brief description"}}

Rules:
- ONLY SELECT statements. Never INSERT, UPDATE, DELETE, DROP, ALTER.
- ALWAYS include WHERE user_id = :user_id in every query.
- Use :user_id as the parameter (not a UUID literal).
- For JSONB: data->>'fieldName' for text, (data->>'fieldName')::numeric for numbers.
- Add ORDER BY and LIMIT where appropriate. Max LIMIT 200.
- If the question cannot be answered: {{"sql": null, "explanation": "Why"}}
"""

SUMMARY_SYSTEM_PROMPT = """You are a helpful health and fitness analyst. The user wears a Garmin
smartwatch and asked a question about their data. Analyze the query results and provide a clear answer.
- Reference specific numbers and dates.
- Spot trends, patterns, or anomalies.
- Give actionable recommendations when appropriate.
- Keep it concise with bullet points.
- Note: you are an AI, not a medical professional."""


def _call_llm(system: str, user_msg: str, model_key: str, max_tokens: int = 1024) -> str:
    """Route LLM call to appropriate backend."""
    model_info = MODELS.get(model_key, MODELS.get(settings.default_model, MODELS["phi4-mini"]))

    if model_info["backend"] == "ollama":
        return _call_ollama(system, user_msg, model_info["model_id"], max_tokens)
    else:
        return _call_anthropic(system, user_msg, model_info["model_id"], max_tokens)


def _call_ollama(system: str, user_msg: str, model_id: str, max_tokens: int) -> str:
    resp = httpx.post(
        f"{OLLAMA_BASE}/api/chat",
        json={
            "model": model_id,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            "stream": False,
            "options": {"num_predict": max_tokens},
        },
        timeout=300.0,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"].strip()


def _call_anthropic(system: str, user_msg: str, model_id: str, max_tokens: int) -> str:
    import anthropic

    api_key = settings.anthropic_api_key
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set. Add it in Settings.")

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model_id, max_tokens=max_tokens,
        system=system, messages=[{"role": "user", "content": user_msg}],
    )
    return response.content[0].text.strip()


def get_available_models() -> list[dict]:
    return [{"id": k, "name": v["name"], "backend": v["backend"]} for k, v in MODELS.items()]


def check_ollama_status() -> dict:
    try:
        resp = httpx.get(f"{OLLAMA_BASE}/api/tags", timeout=5.0)
        resp.raise_for_status()
        return {"running": True, "models": [m["name"] for m in resp.json().get("models", [])]}
    except Exception:
        return {"running": False, "models": []}


async def analyze(
    db: AsyncSession,
    user_id: uuid.UUID,
    question: str,
    model: str | None = None,
    conversation_context: list[dict] | None = None,
) -> str:
    """Analyze health data using text-to-SQL approach."""
    model_key = model or settings.default_model
    today = date.today().isoformat()

    # Step 1: Generate SQL
    sql_prompt = SQL_SYSTEM_PROMPT.replace("{today}", today)
    context_text = ""
    if conversation_context:
        context_text = "\n\nRecent conversation:\n" + "\n".join(
            f"{m['role']}: {m['content'][:200]}" for m in conversation_context[-5:]
        )

    raw_text = _call_llm(sql_prompt, question + context_text, model_key, max_tokens=512)

    # Parse JSON
    if "```" in raw_text:
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        return "I had trouble understanding that question. Could you rephrase it?"

    sql = parsed.get("sql")
    explanation = parsed.get("explanation", "")

    if not sql:
        return f"I can't answer that from the available Garmin data. {explanation}"

    # Validate
    sql_upper = sql.strip().upper()
    if not sql_upper.startswith("SELECT"):
        return "I can only run read-only queries against your data."

    forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "ATTACH"]
    for kw in forbidden:
        if kw in sql_upper.split():
            return "I can only run read-only queries against your data."

    # Step 2: Execute with user_id parameter
    try:
        result = await db.execute(text(sql), {"user_id": user_id})
        columns = list(result.keys()) if result.returns_rows else []
        rows = [dict(zip(columns, row)) for row in result.fetchall()] if columns else []
    except Exception as e:
        logger.warning(f"SQL failed: {e}\nQuery: {sql}")
        return "I had trouble querying your data. Could you rephrase your question?"

    results_text = _format_results(rows, columns)

    # Step 3: Summarize
    summary_user = (
        f"My question: {question}\n\n"
        f"SQL: {sql}\nExplanation: {explanation}\n\n"
        f"Results:\n{results_text}"
    )

    # Save to chat history
    user_msg = ChatMessage(user_id=user_id, role=MessageRole.USER, content=question, model_used=model_key)
    db.add(user_msg)

    answer = _call_llm(SUMMARY_SYSTEM_PROMPT, summary_user, model_key)

    assistant_msg = ChatMessage(
        user_id=user_id, role=MessageRole.ASSISTANT, content=answer,
        sql_query=sql, model_used=model_key,
    )
    db.add(assistant_msg)

    return answer


def _format_results(rows: list[dict], columns: list[str], max_rows: int = 50) -> str:
    if not rows:
        return "(No results)"
    display = rows[:max_rows]
    lines = ["| " + " | ".join(str(c) for c in columns) + " |"]
    lines.append("| " + " | ".join("---" for _ in columns) + " |")
    for row in display:
        lines.append("| " + " | ".join(str(row.get(c, "")) for c in columns) + " |")
    if len(rows) > max_rows:
        lines.append(f"\n... ({len(rows)} total rows, showing first {max_rows})")
    return "\n".join(lines)
```

- [ ] **Step 3: Create backend/app/services/usage.py**

```python
"""Usage tracking and rate limiting for AI queries."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import SubscriptionTier, UsageAction, UsageRecord, Subscription


FREE_TIER_MONTHLY_LIMIT = 5


async def track_usage(
    db: AsyncSession, user_id: uuid.UUID, action: UsageAction, tokens: int = 0
) -> None:
    """Record a usage event."""
    record = UsageRecord(user_id=user_id, action=action, tokens_used=tokens)
    db.add(record)


async def check_ai_quota(db: AsyncSession, user_id: uuid.UUID) -> tuple[bool, int]:
    """Check if user can make an AI query. Returns (allowed, remaining)."""
    # Get subscription tier
    result = await db.execute(
        select(Subscription.tier).where(Subscription.user_id == user_id)
    )
    tier = result.scalar_one_or_none() or SubscriptionTier.FREE

    if tier != SubscriptionTier.FREE:
        return True, -1  # Unlimited

    # Count this month's AI queries
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    result = await db.execute(
        select(func.count(UsageRecord.id))
        .where(UsageRecord.user_id == user_id)
        .where(UsageRecord.action == UsageAction.AI_QUERY)
        .where(UsageRecord.created_at >= month_start)
    )
    count = result.scalar_one()
    remaining = max(0, FREE_TIER_MONTHLY_LIMIT - count)
    return remaining > 0, remaining


async def get_usage_stats(db: AsyncSession, user_id: uuid.UUID) -> dict:
    """Get usage statistics for the current month."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    result = await db.execute(
        select(UsageRecord.action, func.count(UsageRecord.id))
        .where(UsageRecord.user_id == user_id)
        .where(UsageRecord.created_at >= month_start)
        .group_by(UsageRecord.action)
    )
    stats = {row[0].value: row[1] for row in result}
    return {"month": now.strftime("%Y-%m"), "queries": stats}
```

- [ ] **Step 4: Create backend/app/services/sharing.py**

```python
"""Doctor-patient data sharing service."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sharing import AuditLog, DoctorAnnotation, DoctorPatientLink, LinkStatus
from app.models.user import User, UserRole


async def create_invite(
    db: AsyncSession, doctor_id: uuid.UUID, patient_email: str, permissions: dict
) -> DoctorPatientLink:
    """Doctor invites a patient to share data."""
    result = await db.execute(select(User).where(User.email == patient_email))
    patient = result.scalar_one_or_none()
    if patient is None:
        raise ValueError(f"No user found with email {patient_email}")

    link = DoctorPatientLink(
        doctor_id=doctor_id,
        patient_id=patient.id,
        status=LinkStatus.PENDING,
        permissions=permissions,
    )
    db.add(link)

    await _audit(db, doctor_id, "invite_patient", "user", str(patient.id))
    return link


async def accept_invite(
    db: AsyncSession, patient_id: uuid.UUID, link_id: uuid.UUID
) -> DoctorPatientLink:
    """Patient accepts a sharing invite."""
    result = await db.execute(
        select(DoctorPatientLink).where(
            and_(
                DoctorPatientLink.id == link_id,
                DoctorPatientLink.patient_id == patient_id,
                DoctorPatientLink.status == LinkStatus.PENDING,
            )
        )
    )
    link = result.scalar_one_or_none()
    if link is None:
        raise ValueError("Invite not found or already processed")

    link.status = LinkStatus.ACTIVE
    await _audit(db, patient_id, "accept_invite", "link", str(link_id))
    return link


async def revoke_link(
    db: AsyncSession, user_id: uuid.UUID, link_id: uuid.UUID
) -> DoctorPatientLink:
    """Either party can revoke a sharing link."""
    result = await db.execute(
        select(DoctorPatientLink).where(
            and_(
                DoctorPatientLink.id == link_id,
                DoctorPatientLink.status == LinkStatus.ACTIVE,
                (
                    (DoctorPatientLink.doctor_id == user_id)
                    | (DoctorPatientLink.patient_id == user_id)
                ),
            )
        )
    )
    link = result.scalar_one_or_none()
    if link is None:
        raise ValueError("Link not found or already revoked")

    link.status = LinkStatus.REVOKED
    await _audit(db, user_id, "revoke_link", "link", str(link_id))
    return link


async def get_doctor_patients(
    db: AsyncSession, doctor_id: uuid.UUID
) -> list[dict]:
    """Get all active patients for a doctor."""
    result = await db.execute(
        select(DoctorPatientLink, User)
        .join(User, User.id == DoctorPatientLink.patient_id)
        .where(
            and_(
                DoctorPatientLink.doctor_id == doctor_id,
                DoctorPatientLink.status == LinkStatus.ACTIVE,
            )
        )
    )
    return [
        {
            "link_id": str(link.id),
            "patient_id": str(user.id),
            "patient_name": user.name,
            "patient_email": user.email,
            "permissions": link.permissions,
        }
        for link, user in result
    ]


async def get_patient_links(
    db: AsyncSession, patient_id: uuid.UUID
) -> list[dict]:
    """Get all sharing links for a patient."""
    result = await db.execute(
        select(DoctorPatientLink, User)
        .join(User, User.id == DoctorPatientLink.doctor_id)
        .where(DoctorPatientLink.patient_id == patient_id)
    )
    return [
        {
            "link_id": str(link.id),
            "doctor_id": str(user.id),
            "doctor_name": user.name,
            "status": link.status.value,
            "permissions": link.permissions,
        }
        for link, user in result
    ]


async def add_annotation(
    db: AsyncSession, doctor_id: uuid.UUID, patient_id: uuid.UUID,
    content: str, record_id: uuid.UUID | None = None,
) -> DoctorAnnotation:
    """Doctor adds an annotation for a patient."""
    annotation = DoctorAnnotation(
        doctor_id=doctor_id, patient_id=patient_id,
        record_id=record_id, content=content,
    )
    db.add(annotation)
    await _audit(db, doctor_id, "add_annotation", "patient", str(patient_id))
    return annotation


async def _audit(
    db: AsyncSession, user_id: uuid.UUID, action: str,
    target_type: str | None = None, target_id: str | None = None,
) -> None:
    """Record an audit log entry."""
    log = AuditLog(
        user_id=user_id, action=action,
        target_type=target_type, target_id=target_id,
    )
    db.add(log)
```

- [ ] **Step 5: Create backend/app/services/storage.py**

```python
"""File storage service (Cloudflare R2 / S3-compatible)."""

import uuid

import boto3
from botocore.config import Config

from app.core.config import settings


def _get_s3_client():
    """Get S3-compatible client for Cloudflare R2."""
    if not settings.r2_access_key_id:
        raise ValueError("Cloudflare R2 not configured. Set R2_ACCESS_KEY_ID in environment.")

    endpoint = settings.r2_endpoint_url or f"https://{settings.r2_account_id}.r2.cloudflarestorage.com"

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def upload_file(
    file_data: bytes, filename: str, content_type: str, user_id: uuid.UUID
) -> str:
    """Upload a file to R2. Returns the storage key."""
    client = _get_s3_client()
    key = f"users/{user_id}/records/{uuid.uuid4()}/{filename}"
    client.put_object(
        Bucket=settings.r2_bucket_name,
        Key=key,
        Body=file_data,
        ContentType=content_type,
    )
    return key


def get_download_url(storage_key: str, expires_in: int = 3600) -> str:
    """Generate a presigned download URL."""
    client = _get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.r2_bucket_name, "Key": storage_key},
        ExpiresIn=expires_in,
    )


def delete_file(storage_key: str) -> None:
    """Delete a file from R2."""
    client = _get_s3_client()
    client.delete_object(Bucket=settings.r2_bucket_name, Key=storage_key)
```

- [ ] **Step 6: Create backend/app/services/billing.py**

```python
"""Stripe billing service."""

import uuid

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.billing import Subscription, SubscriptionStatus, SubscriptionTier
from app.models.user import User

TIER_PRICE_MAP = {
    SubscriptionTier.PRO: "price_pro_monthly",        # Replace with real Stripe price ID
    SubscriptionTier.PRO_DOCTOR: "price_pro_doctor",
    SubscriptionTier.DOCTOR: "price_doctor",
}


def _get_stripe():
    """Initialize Stripe with secret key."""
    if not settings.stripe_secret_key:
        raise ValueError("Stripe not configured. Set STRIPE_SECRET_KEY in environment.")
    stripe.api_key = settings.stripe_secret_key
    return stripe


async def create_checkout_session(
    db: AsyncSession, user_id: uuid.UUID, tier: SubscriptionTier, success_url: str, cancel_url: str
) -> str:
    """Create a Stripe checkout session. Returns the checkout URL."""
    s = _get_stripe()

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one()

    # Get or create Stripe customer
    result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
    sub = result.scalar_one_or_none()

    if sub and sub.stripe_customer_id:
        customer_id = sub.stripe_customer_id
    else:
        customer = s.Customer.create(email=user.email, metadata={"user_id": str(user_id)})
        customer_id = customer.id
        if sub is None:
            sub = Subscription(user_id=user_id, stripe_customer_id=customer_id)
            db.add(sub)
        else:
            sub.stripe_customer_id = customer_id

    price_id = TIER_PRICE_MAP.get(tier)
    if not price_id:
        raise ValueError(f"No price configured for tier {tier}")

    session = s.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"user_id": str(user_id), "tier": tier.value},
    )
    return session.url


async def handle_webhook(db: AsyncSession, payload: bytes, sig_header: str) -> None:
    """Handle Stripe webhook events."""
    s = _get_stripe()
    event = s.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = uuid.UUID(session["metadata"]["user_id"])
        tier = SubscriptionTier(session["metadata"]["tier"])

        result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
        sub = result.scalar_one_or_none()
        if sub:
            sub.stripe_subscription_id = session.get("subscription")
            sub.tier = tier
            sub.status = SubscriptionStatus.ACTIVE

    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        result = await db.execute(
            select(Subscription).where(
                Subscription.stripe_subscription_id == subscription["id"]
            )
        )
        sub = result.scalar_one_or_none()
        if sub:
            sub.tier = SubscriptionTier.FREE
            sub.status = SubscriptionStatus.CANCELED

    elif event["type"] == "invoice.payment_failed":
        invoice = event["data"]["object"]
        sub_id = invoice.get("subscription")
        if sub_id:
            result = await db.execute(
                select(Subscription).where(Subscription.stripe_subscription_id == sub_id)
            )
            sub = result.scalar_one_or_none()
            if sub:
                sub.status = SubscriptionStatus.PAST_DUE


async def get_subscription(db: AsyncSession, user_id: uuid.UUID) -> dict:
    """Get current subscription info."""
    result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
    sub = result.scalar_one_or_none()
    if sub is None:
        return {"tier": "free", "status": "active"}
    return {
        "tier": sub.tier.value,
        "status": sub.status.value,
        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
    }


async def cancel_subscription(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Cancel the user's Stripe subscription."""
    s = _get_stripe()
    result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
    sub = result.scalar_one_or_none()
    if sub and sub.stripe_subscription_id:
        s.Subscription.modify(sub.stripe_subscription_id, cancel_at_period_end=True)
        sub.status = SubscriptionStatus.CANCELED
```

- [ ] **Step 7: Create empty backend/app/services/__init__.py**

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/
git commit -m "feat: add all backend services (sync, LLM, usage, sharing, storage, billing)"
```

---

### Task A5: API route handlers

**Files:**
- Create: `backend/app/api/health.py`
- Create: `backend/app/api/auth.py`
- Create: `backend/app/api/doctor.py`
- Create: `backend/app/api/billing.py`
- Create: `backend/app/api/voice.py`

- [ ] **Step 1: Create backend/app/api/health.py**

```python
"""Health data API endpoints."""

import io
import json
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.health import Activity, DailyStat, HeartRateRecord, SleepRecord
from app.models.user import User
from app.services import llm_analyzer as llm
from app.services import usage
from app.services.garmin_sync import sync_user_data
from app.models.billing import UsageAction

router = APIRouter()


class SyncRequest(BaseModel):
    days: int = 7


class AskRequest(BaseModel):
    question: str
    model: str | None = None
    days: int = 30


@router.post("/sync")
async def sync_data(
    body: SyncRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        results = await sync_user_data(db, user.id, days=body.days)
        await usage.track_usage(db, user.id, UsageAction.SYNC)
        return {"status": "ok", "results": results}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ask")
async def ask_question(
    body: AskRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="No question provided")

    allowed, remaining = await usage.check_ai_quota(db, user.id)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Monthly AI query limit reached. Upgrade to Pro for unlimited queries.",
        )

    answer = await llm.analyze(db, user.id, body.question, model=body.model)
    await usage.track_usage(db, user.id, UsageAction.AI_QUERY)
    return {"answer": answer, "remaining_queries": remaining - 1 if remaining > 0 else -1}


@router.get("/chart/{metric}")
async def get_chart(
    metric: str,
    days: int = 30,
    user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    if metric == "steps":
        stmt = (
            select(DailyStat.date, DailyStat.data["totalSteps"].as_float().label("value"))
            .where(DailyStat.user_id == user.id)
            .order_by(DailyStat.date.desc())
            .limit(days)
        )
    elif metric == "calories":
        stmt = (
            select(DailyStat.date, DailyStat.data["totalKilocalories"].as_float().label("value"))
            .where(DailyStat.user_id == user.id)
            .order_by(DailyStat.date.desc())
            .limit(days)
        )
    elif metric == "resting_hr":
        stmt = (
            select(HeartRateRecord.date, HeartRateRecord.resting_hr.label("value"))
            .where(HeartRateRecord.user_id == user.id)
            .order_by(HeartRateRecord.date.desc())
            .limit(days)
        )
    elif metric == "sleep":
        stmt = (
            select(SleepRecord.date, (SleepRecord.duration_seconds / 3600.0).label("value"))
            .where(SleepRecord.user_id == user.id)
            .order_by(SleepRecord.date.desc())
            .limit(days)
        )
    elif metric == "stress":
        stmt = (
            select(DailyStat.date, DailyStat.data["averageStressLevel"].as_float().label("value"))
            .where(DailyStat.user_id == user.id)
            .order_by(DailyStat.date.desc())
            .limit(days)
        )
    else:
        return {"metric": metric, "data": []}

    result = await db.execute(stmt)
    rows = result.all()
    data = [{"date": r.date, "value": r.value} for r in reversed(rows) if r.value is not None]
    return {"metric": metric, "data": data}


@router.get("/stats")
async def get_stats(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from sqlalchemy import func

    total_days = await db.scalar(
        select(func.count(DailyStat.id)).where(DailyStat.user_id == user.id)
    )
    total_activities = await db.scalar(
        select(func.count(Activity.id)).where(Activity.user_id == user.id)
    )
    min_date = await db.scalar(
        select(func.min(DailyStat.date)).where(DailyStat.user_id == user.id)
    )
    max_date = await db.scalar(
        select(func.max(DailyStat.date)).where(DailyStat.user_id == user.id)
    )

    usage_stats = await usage.get_usage_stats(db, user.id)

    return {
        "total_days": total_days or 0,
        "total_activities": total_activities or 0,
        "date_range": {"min": min_date, "max": max_date},
        "usage": usage_stats,
    }


@router.get("/models")
async def get_models():
    models = llm.get_available_models()
    ollama = llm.check_ollama_status()
    return {"models": models, "ollama": ollama}


@router.get("/export")
async def export_data(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """GDPR Article 20 — data portability. Export all user data as ZIP."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Daily stats
        result = await db.execute(
            select(DailyStat).where(DailyStat.user_id == user.id).order_by(DailyStat.date)
        )
        stats = [{"date": r.date, "data": r.data} for r in result.scalars()]
        zf.writestr("daily_stats.json", json.dumps(stats, indent=2, default=str))

        # Activities
        result = await db.execute(
            select(Activity).where(Activity.user_id == user.id).order_by(Activity.date)
        )
        activities = [
            {"id": r.id, "date": r.date, "type": r.activity_type, "name": r.name, "data": r.data}
            for r in result.scalars()
        ]
        zf.writestr("activities.json", json.dumps(activities, indent=2, default=str))

        # Sleep
        result = await db.execute(
            select(SleepRecord).where(SleepRecord.user_id == user.id).order_by(SleepRecord.date)
        )
        sleep = [{"date": r.date, "duration_seconds": r.duration_seconds, "data": r.data} for r in result.scalars()]
        zf.writestr("sleep.json", json.dumps(sleep, indent=2, default=str))

        # Heart rate
        result = await db.execute(
            select(HeartRateRecord).where(HeartRateRecord.user_id == user.id).order_by(HeartRateRecord.date)
        )
        hr = [{"date": r.date, "resting_hr": r.resting_hr, "data": r.data} for r in result.scalars()]
        zf.writestr("heart_rate.json", json.dumps(hr, indent=2, default=str))

    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=garmintracker-export-{user.id}.zip"},
    )


@router.delete("/account")
async def delete_account(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """GDPR Article 17 — right to erasure. Delete all user data."""
    await db.delete(user)  # Cascade deletes all related data
    return {"status": "ok", "message": "Account and all data deleted"}
```

- [ ] **Step 2: Create backend/app/api/auth.py**

```python
"""Authentication endpoints (Auth0)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import encrypt_value, get_current_user
from app.models.user import GarminCredential, User

router = APIRouter()


@router.get("/me")
async def get_me(user: Annotated[User, Depends(get_current_user)]):
    """Get current user info."""
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": user.role.value,
        "has_garmin": user.garmin_credential is not None,
    }


@router.get("/config")
async def get_auth_config():
    """Return Auth0 config for the frontend (public info only)."""
    return {
        "domain": settings.auth0_domain,
        "clientId": settings.auth0_client_id,
        "audience": settings.auth0_audience,
        "configured": bool(settings.auth0_domain and settings.auth0_client_id),
    }


class GarminSetup(BaseModel):
    email: str
    password: str


@router.post("/garmin/connect")
async def connect_garmin(
    body: GarminSetup,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Save encrypted Garmin credentials for the user."""
    if user.garmin_credential:
        user.garmin_credential.encrypted_email = encrypt_value(body.email)
        user.garmin_credential.encrypted_password = encrypt_value(body.password)
    else:
        cred = GarminCredential(
            user_id=user.id,
            encrypted_email=encrypt_value(body.email),
            encrypted_password=encrypt_value(body.password),
        )
        db.add(cred)
    return {"status": "ok", "message": "Garmin credentials saved"}


@router.post("/garmin/disconnect")
async def disconnect_garmin(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Remove Garmin credentials."""
    if user.garmin_credential:
        await db.delete(user.garmin_credential)
    return {"status": "ok"}
```

- [ ] **Step 3: Create backend/app/api/doctor.py**

```python
"""Doctor portal API endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.health import Activity, DailyStat, HeartRateRecord, SleepRecord
from app.models.sharing import DoctorPatientLink, LinkStatus, MedicalRecord
from app.models.user import User, UserRole
from app.services import sharing, storage

router = APIRouter()


class InviteRequest(BaseModel):
    patient_email: str
    permissions: dict = {"sleep": True, "vitals": True, "activities": True, "stats": True}


class AnnotationRequest(BaseModel):
    content: str
    record_id: str | None = None


@router.get("/patients")
async def list_patients(
    user: Annotated[User, Depends(require_role(UserRole.DOCTOR))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    patients = await sharing.get_doctor_patients(db, user.id)
    return {"patients": patients}


@router.post("/invite")
async def invite_patient(
    body: InviteRequest,
    user: Annotated[User, Depends(require_role(UserRole.DOCTOR))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        link = await sharing.create_invite(db, user.id, body.patient_email, body.permissions)
        return {"status": "ok", "link_id": str(link.id)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/patients/{patient_id}/data")
async def get_patient_data(
    patient_id: uuid.UUID,
    user: Annotated[User, Depends(require_role(UserRole.DOCTOR))],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = 30,
):
    """View patient data (filtered by sharing permissions)."""
    # Verify active link exists
    result = await db.execute(
        select(DoctorPatientLink).where(
            DoctorPatientLink.doctor_id == user.id,
            DoctorPatientLink.patient_id == patient_id,
            DoctorPatientLink.status == LinkStatus.ACTIVE,
        )
    )
    link = result.scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=403, detail="No active sharing link with this patient")

    perms = link.permissions
    data = {}

    if perms.get("stats"):
        result = await db.execute(
            select(DailyStat)
            .where(DailyStat.user_id == patient_id)
            .order_by(DailyStat.date.desc())
            .limit(days)
        )
        data["daily_stats"] = [{"date": r.date, "data": r.data} for r in result.scalars()]

    if perms.get("activities"):
        result = await db.execute(
            select(Activity)
            .where(Activity.user_id == patient_id)
            .order_by(Activity.date.desc())
            .limit(days * 3)
        )
        data["activities"] = [
            {"date": r.date, "type": r.activity_type, "name": r.name,
             "duration": r.duration_seconds, "calories": r.calories}
            for r in result.scalars()
        ]

    if perms.get("sleep"):
        result = await db.execute(
            select(SleepRecord)
            .where(SleepRecord.user_id == patient_id)
            .order_by(SleepRecord.date.desc())
            .limit(days)
        )
        data["sleep"] = [
            {"date": r.date, "duration": r.duration_seconds, "deep": r.deep_seconds, "rem": r.rem_seconds}
            for r in result.scalars()
        ]

    if perms.get("vitals"):
        result = await db.execute(
            select(HeartRateRecord)
            .where(HeartRateRecord.user_id == patient_id)
            .order_by(HeartRateRecord.date.desc())
            .limit(days)
        )
        data["heart_rate"] = [
            {"date": r.date, "resting_hr": r.resting_hr, "max_hr": r.max_hr}
            for r in result.scalars()
        ]

    return {"patient_id": str(patient_id), "data": data}


@router.post("/patients/{patient_id}/annotations")
async def add_annotation(
    patient_id: uuid.UUID,
    body: AnnotationRequest,
    user: Annotated[User, Depends(require_role(UserRole.DOCTOR))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    record_id = uuid.UUID(body.record_id) if body.record_id else None
    annotation = await sharing.add_annotation(db, user.id, patient_id, body.content, record_id)
    return {"status": "ok", "annotation_id": str(annotation.id)}


@router.post("/patients/{patient_id}/records")
async def upload_record(
    patient_id: uuid.UUID,
    file: UploadFile,
    user: Annotated[User, Depends(require_role(UserRole.DOCTOR))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Upload a medical record for a patient."""
    data = await file.read()
    try:
        key = storage.upload_file(data, file.filename, file.content_type, patient_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    record = MedicalRecord(
        user_id=patient_id,
        uploaded_by=user.id,
        filename=file.filename,
        storage_key=key,
        content_type=file.content_type,
        size_bytes=len(data),
    )
    db.add(record)
    return {"status": "ok", "record_id": str(record.id)}


@router.get("/patients/{patient_id}/records")
async def list_records(
    patient_id: uuid.UUID,
    user: Annotated[User, Depends(require_role(UserRole.DOCTOR))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(MedicalRecord)
        .where(MedicalRecord.user_id == patient_id)
        .order_by(MedicalRecord.created_at.desc())
    )
    records = [
        {
            "id": str(r.id), "filename": r.filename,
            "content_type": r.content_type, "size_bytes": r.size_bytes,
            "created_at": r.created_at.isoformat(),
        }
        for r in result.scalars()
    ]
    return {"records": records}
```

- [ ] **Step 4: Create backend/app/api/billing.py**

```python
"""Billing API endpoints (Stripe)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.billing import SubscriptionTier
from app.models.user import User
from app.services import billing

router = APIRouter()


class CheckoutRequest(BaseModel):
    tier: str
    success_url: str = "http://localhost:3000/dashboard/settings?billing=success"
    cancel_url: str = "http://localhost:3000/dashboard/settings?billing=cancel"


@router.post("/create-checkout")
async def create_checkout(
    body: CheckoutRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        tier = SubscriptionTier(body.tier)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid tier: {body.tier}")

    try:
        url = await billing.create_checkout_session(
            db, user.id, tier, body.success_url, body.cancel_url
        )
        return {"checkout_url": url}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        await billing.handle_webhook(db, payload, sig)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/subscription")
async def get_subscription(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await billing.get_subscription(db, user.id)


@router.post("/cancel")
async def cancel_subscription(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        await billing.cancel_subscription(db, user.id)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

- [ ] **Step 5: Create backend/app/api/voice.py** (streaming SSE endpoint)

```python
"""Voice/streaming API endpoints."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services import llm_analyzer as llm
from app.services import usage
from app.models.billing import UsageAction

router = APIRouter()


class StreamRequest(BaseModel):
    question: str
    model: str | None = None


@router.post("/ask/stream")
async def ask_stream(
    body: StreamRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Stream AI response via Server-Sent Events."""
    allowed, _ = await usage.check_ai_quota(db, user.id)
    if not allowed:
        async def error_gen():
            yield {"event": "error", "data": json.dumps({"message": "Monthly limit reached"})}
        return EventSourceResponse(error_gen())

    async def generate():
        # For now, get the full answer and stream it word-by-word
        # TODO: Replace with actual Anthropic streaming when available
        answer = await llm.analyze(db, user.id, body.question, model=body.model)
        await usage.track_usage(db, user.id, UsageAction.AI_QUERY)

        words = answer.split()
        buffer = ""
        for word in words:
            buffer += word + " "
            if len(buffer) > 20:
                yield {"event": "token", "data": json.dumps({"text": buffer})}
                buffer = ""
        if buffer:
            yield {"event": "token", "data": json.dumps({"text": buffer})}
        yield {"event": "done", "data": json.dumps({"complete": True})}

    return EventSourceResponse(generate())
```

- [ ] **Step 6: Create backend/app/api/sharing.py** (patient-side sharing endpoints)

```python
"""Patient-side sharing endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services import sharing

router = APIRouter()


@router.get("/links")
async def list_links(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    links = await sharing.get_patient_links(db, user.id)
    return {"links": links}


@router.post("/accept/{link_id}")
async def accept_invite(
    link_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        await sharing.accept_invite(db, user.id, link_id)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/revoke/{link_id}")
async def revoke_link(
    link_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        await sharing.revoke_link(db, user.id, link_id)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

- [ ] **Step 7: Update backend/app/main.py to include all routers**

Add the voice and sharing routers:
```python
    from app.api.voice import router as voice_router
    app.include_router(voice_router, prefix="/api/health", tags=["voice"])

    from app.api.sharing import router as sharing_router
    app.include_router(sharing_router, prefix="/api/sharing", tags=["sharing"])
```

Also add security headers middleware:
```python
from app.core.middleware import SecurityHeadersMiddleware, setup_rate_limiting
```

- [ ] **Step 8: Create backend/app/core/middleware.py**

```python
"""Security middleware — headers, rate limiting."""

from fastapi import FastAPI, Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

limiter = Limiter(key_func=get_remote_address)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


def setup_rate_limiting(app: FastAPI) -> None:
    """Configure rate limiting on sensitive endpoints."""
    app.state.limiter = limiter
```

- [ ] **Step 9: Commit**

```bash
git add backend/app/api/ backend/app/core/middleware.py
git commit -m "feat: add all API route handlers (health, auth, doctor, billing, voice, sharing)"
```

---

### Task A6: Docker + docker-compose with PostgreSQL

**Files:**
- Create: `backend/Dockerfile`
- Create: `docker-compose.yml` (root)
- Create: `.env.example` (root)

- [ ] **Step 1: Create backend/Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY app/ app/
COPY migrations/ migrations/
COPY alembic.ini ./

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create docker-compose.yml (root)**

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: garmintracker
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file:
      - .env
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/garmintracker
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
    depends_on:
      - backend

volumes:
  pgdata:
```

- [ ] **Step 3: Create .env.example (root)**

```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/garmintracker

# Auth0 (create free account at https://auth0.com)
AUTH0_DOMAIN=your-tenant.auth0.com
AUTH0_CLIENT_ID=
AUTH0_CLIENT_SECRET=
AUTH0_AUDIENCE=https://api.garmintracker.com

# Stripe (create account at https://stripe.com)
STRIPE_SECRET_KEY=
STRIPE_PUBLISHABLE_KEY=
STRIPE_WEBHOOK_SECRET=

# Cloudflare R2 (create account at https://cloudflare.com)
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=garmintracker-uploads

# Garmin (dev mode — in production, per-user encrypted in DB)
GARMIN_EMAIL=
GARMIN_PASSWORD=

# AI
ANTHROPIC_API_KEY=

# Security
ENCRYPTION_KEY=  # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# App
DEBUG=true
LOG_LEVEL=INFO
CORS_ORIGINS=["http://localhost:3000"]
```

- [ ] **Step 4: Commit**

```bash
git add backend/Dockerfile docker-compose.yml .env.example
git commit -m "feat: add Docker setup with PostgreSQL 16, backend, and frontend services"
```

---

## Task Group B: Next.js Frontend (Phase 4 frontend + dashboard)

### Task B1: Scaffold Next.js project

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/next.config.ts`
- Create: `frontend/postcss.config.js`
- Create: `frontend/app/layout.tsx`
- Create: `frontend/app/globals.css`
- Create: `frontend/Dockerfile`

- [ ] **Step 1: Create frontend/package.json**

```json
{
  "name": "garmintracker-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "^14.2",
    "react": "^18.3",
    "react-dom": "^18.3",
    "@auth0/nextjs-auth0": "^3.5",
    "recharts": "^2.13",
    "lucide-react": "^0.468",
    "clsx": "^2.1",
    "tailwind-merge": "^2.6"
  },
  "devDependencies": {
    "typescript": "^5.7",
    "@types/react": "^18.3",
    "@types/react-dom": "^18.3",
    "tailwindcss": "^3.4",
    "postcss": "^8.4",
    "autoprefixer": "^10.4",
    "eslint": "^8.57",
    "eslint-config-next": "^14.2"
  }
}
```

- [ ] **Step 2: Create frontend/tsconfig.json**

```json
{
  "compilerOptions": {
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 3: Create frontend/tailwind.config.ts, postcss.config.js, next.config.ts**

tailwind.config.ts:
```typescript
import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: { DEFAULT: "#4fc3f7", dark: "#0f1117", card: "#1a1d27", border: "#2a2d37" },
      },
    },
  },
  plugins: [],
};
export default config;
```

postcss.config.js:
```javascript
module.exports = { plugins: { tailwindcss: {}, autoprefixer: {} } };
```

next.config.ts:
```typescript
import type { NextConfig } from "next";

const config: NextConfig = {
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/:path*` },
    ];
  },
};
export default config;
```

- [ ] **Step 4: Create frontend/app/globals.css**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  background: #0f1117;
  color: #e0e0e0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}
```

- [ ] **Step 5: Create frontend/app/layout.tsx**

```tsx
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "GarminTracker",
  description: "AI-powered health insights from your Garmin watch",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
```

- [ ] **Step 6: Create frontend/Dockerfile**

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

FROM node:20-alpine
WORKDIR /app
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./
COPY --from=builder /app/public ./public
ENV NODE_ENV=production
EXPOSE 3000
CMD ["npm", "start"]
```

- [ ] **Step 7: Commit**

```bash
git add frontend/
git commit -m "feat: scaffold Next.js 14 frontend with TypeScript, Tailwind CSS"
```

---

### Task B2: Frontend API client + auth + types

**Files:**
- Create: `frontend/lib/api.ts`
- Create: `frontend/lib/types.ts`
- Create: `frontend/lib/auth.tsx`

- [ ] **Step 1: Create frontend/lib/types.ts**

```typescript
export interface User {
  id: string;
  email: string;
  name: string;
  role: "patient" | "doctor";
  has_garmin: boolean;
}

export interface ChartDataPoint {
  date: string;
  value: number;
}

export interface StatsResponse {
  total_days: number;
  total_activities: number;
  date_range: { min: string | null; max: string | null };
  usage: { month: string; queries: Record<string, number> };
}

export interface AskResponse {
  answer: string;
  remaining_queries: number;
}

export interface SyncResult {
  date: string;
  daily_stats: boolean | string;
  activities: number | string;
  sleep: boolean | string;
  heart_rate: boolean | string;
}

export interface ModelInfo {
  id: string;
  name: string;
  backend: "ollama" | "anthropic";
}

export interface PatientSummary {
  link_id: string;
  patient_id: string;
  patient_name: string;
  patient_email: string;
  permissions: Record<string, boolean>;
}

export interface SubscriptionInfo {
  tier: string;
  status: string;
  current_period_end: string | null;
}

export interface SharingLink {
  link_id: string;
  doctor_id: string;
  doctor_name: string;
  status: string;
  permissions: Record<string, boolean>;
}
```

- [ ] **Step 2: Create frontend/lib/api.ts**

```typescript
import type {
  AskResponse, ChartDataPoint, ModelInfo, PatientSummary,
  StatsResponse, SubscriptionInfo, SyncResult, User, SharingLink,
} from "./types";

const API = process.env.NEXT_PUBLIC_API_URL || "";

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API}${path}`, { ...options, headers: { ...headers, ...options?.headers } });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || body.message || `API error ${res.status}`);
  }
  return res.json();
}

// Auth
export const getMe = () => fetchApi<User>("/api/auth/me");
export const getAuthConfig = () => fetchApi<{ domain: string; clientId: string; audience: string; configured: boolean }>("/api/auth/config");
export const connectGarmin = (email: string, password: string) => fetchApi("/api/auth/garmin/connect", { method: "POST", body: JSON.stringify({ email, password }) });
export const disconnectGarmin = () => fetchApi("/api/auth/garmin/disconnect", { method: "POST" });

// Health
export const syncData = (days: number) => fetchApi<{ status: string; results: SyncResult[] }>("/api/health/sync", { method: "POST", body: JSON.stringify({ days }) });
export const askQuestion = (question: string, model?: string) => fetchApi<AskResponse>("/api/health/ask", { method: "POST", body: JSON.stringify({ question, model }) });
export const getChart = (metric: string, days = 30) => fetchApi<{ metric: string; data: ChartDataPoint[] }>(`/api/health/chart/${metric}?days=${days}`);
export const getStats = () => fetchApi<StatsResponse>("/api/health/stats");
export const getModels = () => fetchApi<{ models: ModelInfo[]; ollama: { running: boolean; models: string[] } }>("/api/health/models");
export const exportData = () => fetch(`${API}/api/health/export`, { headers: { Authorization: `Bearer ${localStorage.getItem("token")}` } });

// Doctor
export const getDoctorPatients = () => fetchApi<{ patients: PatientSummary[] }>("/api/doctor/patients");
export const invitePatient = (email: string, permissions: Record<string, boolean>) => fetchApi("/api/doctor/invite", { method: "POST", body: JSON.stringify({ patient_email: email, permissions }) });
export const getPatientData = (patientId: string, days = 30) => fetchApi<{ patient_id: string; data: Record<string, unknown[]> }>(`/api/doctor/patients/${patientId}/data?days=${days}`);

// Sharing
export const getSharingLinks = () => fetchApi<{ links: SharingLink[] }>("/api/sharing/links");
export const acceptInvite = (linkId: string) => fetchApi("/api/sharing/accept/" + linkId, { method: "POST" });
export const revokeLink = (linkId: string) => fetchApi("/api/sharing/revoke/" + linkId, { method: "POST" });

// Billing
export const getSubscription = () => fetchApi<SubscriptionInfo>("/api/billing/subscription");
export const createCheckout = (tier: string) => fetchApi<{ checkout_url: string }>("/api/billing/create-checkout", { method: "POST", body: JSON.stringify({ tier }) });
export const cancelSubscription = () => fetchApi("/api/billing/cancel", { method: "POST" });
```

- [ ] **Step 3: Create frontend/lib/auth.tsx**

```tsx
"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import type { User } from "./types";
import { getAuthConfig, getMe } from "./api";

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: () => void;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType>({
  user: null, loading: true, login: () => {}, logout: () => {}, isAuthenticated: false,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check for existing token
    const token = localStorage.getItem("token");
    if (token) {
      getMe()
        .then(setUser)
        .catch(() => localStorage.removeItem("token"))
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = async () => {
    const config = await getAuthConfig();
    if (!config.configured) {
      // Dev mode: auto-login with dev token
      localStorage.setItem("token", "dev-token");
      const me = await getMe();
      setUser(me);
      return;
    }
    // Auth0 redirect
    const params = new URLSearchParams({
      client_id: config.clientId,
      redirect_uri: window.location.origin + "/callback",
      response_type: "token",
      scope: "openid profile email",
      audience: config.audience,
    });
    window.location.href = `https://${config.domain}/authorize?${params}`;
  };

  const logout = () => {
    localStorage.removeItem("token");
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, isAuthenticated: !!user }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
```

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/
git commit -m "feat: add frontend API client, TypeScript types, and Auth0 auth provider"
```

---

### Task B3: Dashboard pages (patient view)

**Files:**
- Create: `frontend/app/page.tsx` (landing)
- Create: `frontend/app/(auth)/callback/page.tsx`
- Create: `frontend/app/dashboard/layout.tsx`
- Create: `frontend/app/dashboard/page.tsx`
- Create: `frontend/app/dashboard/ask/page.tsx`
- Create: `frontend/app/dashboard/settings/page.tsx`
- Create: `frontend/components/charts/TrendChart.tsx`
- Create: `frontend/components/shared/StatsBar.tsx`

- [ ] **Step 1-8: Create all dashboard page files** (see spec for UI details — each page is a React component calling the API client)

These files implement:
- Landing page with login button
- Auth callback handler (parses token from URL hash)
- Dashboard layout with sidebar navigation
- Main dashboard: stats bar + trend charts + sync button
- AI chat page: question input + model selector + answer display + voice buttons (Web Speech API)
- Settings page: Garmin connect/disconnect, subscription management, data export, account deletion

- [ ] **Step 9: Commit**

```bash
git add frontend/app/ frontend/components/
git commit -m "feat: add all frontend pages (landing, dashboard, AI chat, settings)"
```

---

### Task B4: Doctor portal pages

**Files:**
- Create: `frontend/app/doctor/layout.tsx`
- Create: `frontend/app/doctor/page.tsx`
- Create: `frontend/app/doctor/[patientId]/page.tsx`

- [ ] **Step 1-4: Create doctor portal pages**

These implement:
- Doctor layout (checks role === "doctor")
- Patient list with invite button
- Patient detail view: shared health data charts + annotations + record uploads

- [ ] **Step 5: Commit**

```bash
git add frontend/app/doctor/
git commit -m "feat: add doctor portal pages (patient list, patient detail, annotations)"
```

---

## Task Group C: Mobile App Scaffold (Phase 7)

### Task C1: Expo project scaffold

**Files:**
- Create: `mobile/package.json`
- Create: `mobile/app.json`
- Create: `mobile/tsconfig.json`
- Create: `mobile/app/_layout.tsx`
- Create: `mobile/app/index.tsx`
- Create: `mobile/app/ask.tsx`
- Create: `mobile/app/settings.tsx`
- Create: `mobile/lib/api.ts`
- Create: `mobile/lib/auth.ts`

- [ ] **Step 1-5: Create Expo scaffold**

package.json with expo, expo-router, expo-auth-session, react-native-chart-kit dependencies.
app.json with GarminTracker name and config.
Same API client pattern as frontend/lib/api.ts.
Auth using expo-auth-session with Auth0.
Three screens: Dashboard (stats + charts), AI Chat, Settings.

- [ ] **Step 6: Commit**

```bash
git add mobile/
git commit -m "feat: scaffold Expo mobile app with auth, dashboard, and AI chat screens"
```

---

## Task Group D: CI/CD + Tests

### Task D1: Backend tests

**Files:**
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_health_api.py`
- Create: `backend/tests/test_usage.py`
- Create: `backend/tests/test_sharing.py`
- Create: `backend/tests/test_models.py`

- [ ] **Step 1-5: Write tests for core backend functionality**

Test fixtures with async SQLAlchemy + test PostgreSQL (or SQLite for unit tests).
Tests for: usage tracking/quota, sharing invite/accept/revoke flow, API endpoints with mocked auth.

- [ ] **Step 6: Commit**

```bash
git add backend/tests/
git commit -m "test: add backend tests for health API, usage, sharing, and models"
```

---

### Task D2: Updated CI pipeline

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create .github/workflows/ci.yml**

Jobs: backend lint + test + typecheck, frontend lint + build, Docker build.
Backend tests use PostgreSQL service container.

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: update GitHub Actions for monorepo (backend + frontend + Docker)"
```

---

## Task Group E: Cleanup

### Task E1: Update root files and clean up old code

- [ ] **Step 1: Update .gitignore for monorepo**
- [ ] **Step 2: Keep old garmin_tracker/ directory for reference (or remove)**
- [ ] **Step 3: Update root README placeholder**
- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "chore: monorepo cleanup, update gitignore and root files"
```
