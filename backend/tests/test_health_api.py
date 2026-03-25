"""Tests for health API endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_ping(client: AsyncClient):
    resp = await client.get("/api/ping")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "test@example.com"
    assert data["role"] == "PATIENT"


@pytest.mark.asyncio
async def test_get_auth_config(client: AsyncClient):
    resp = await client.get("/api/auth/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "domain" in data
    assert "client_id" in data


@pytest.mark.asyncio
async def test_get_stats(client: AsyncClient):
    resp = await client.get("/api/health/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "tier" in data
    assert data["tier"] == "FREE"


@pytest.mark.asyncio
async def test_list_models(client: AsyncClient):
    resp = await client.get("/api/health/models")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_chart_requires_params(client: AsyncClient):
    resp = await client.get("/api/health/chart/totalSteps")
    # Missing required query params
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_account(client: AsyncClient):
    resp = await client.delete("/api/health/account")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"
