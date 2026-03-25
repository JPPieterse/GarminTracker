"""Shared test fixtures: async DB session, test client, test user."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.base import Base
from app.models.user import User, UserRole

# Use aiosqlite for tests (no Postgres required)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create all tables and yield a fresh session per test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with TestSessionLocal() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create and return a test patient user."""
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        name="Test User",
        auth_provider="dev",
        auth_subject="local",
        role=UserRole.PATIENT,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def doctor_user(db_session: AsyncSession) -> User:
    """Create and return a test doctor user."""
    user = User(
        id=uuid.uuid4(),
        email="doctor@example.com",
        name="Dr. Test",
        auth_provider="dev",
        auth_subject="doctor",
        role=UserRole.DOCTOR,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, test_user: User) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client with DB and auth overrides."""
    from app.main import app

    async def _override_db():
        yield db_session

    async def _override_user():
        return test_user

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def doctor_client(db_session: AsyncSession, doctor_user: User) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client authenticated as a doctor."""
    from app.main import app

    async def _override_db():
        yield db_session

    async def _override_user():
        return doctor_user

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
