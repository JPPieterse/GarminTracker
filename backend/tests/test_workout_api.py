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
