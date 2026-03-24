"""Integration tests for the FastAPI application endpoints."""

from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from garmin_tracker import database as db


@pytest.fixture()
def test_app(test_db):
    """Create a test app with isolated database."""
    from garmin_tracker.app import app

    return app


@pytest_asyncio.fixture()
async def client(test_app):
    """Async HTTP client for testing API endpoints."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_api_stats_empty(client):
    resp = await client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_days"] == 0
    assert data["total_activities"] == 0
    assert data["date_range"]["min"] is None


@pytest.mark.asyncio
async def test_api_stats_with_data(client, test_db):
    db.save_daily_stats("2024-01-15", {"totalSteps": 8000})
    db.save_activity(
        {
            "activityId": 1,
            "startTimeLocal": "2024-01-15 08:00:00",
            "activityType": {"typeKey": "running"},
            "activityName": "Run",
            "duration": 1800,
            "distance": 5000,
            "calories": 300,
            "averageHR": 145,
            "maxHR": 170,
        }
    )
    resp = await client.get("/api/stats")
    data = resp.json()
    assert data["total_days"] == 1
    assert data["total_activities"] == 1
    assert data["date_range"]["min"] == "2024-01-15"


@pytest.mark.asyncio
async def test_api_chart_steps(client, test_db):
    db.save_daily_stats("2024-01-15", {"totalSteps": 8000})
    db.save_daily_stats("2024-01-16", {"totalSteps": 10000})
    resp = await client.get("/api/chart/steps?days=30")
    assert resp.status_code == 200
    data = resp.json()
    assert data["metric"] == "steps"
    assert len(data["data"]) == 2


@pytest.mark.asyncio
async def test_api_chart_unknown_metric(client):
    resp = await client.get("/api/chart/bogus?days=30")
    assert resp.status_code == 200
    assert resp.json()["data"] == []


@pytest.mark.asyncio
async def test_api_ask_empty_question(client):
    resp = await client.post("/api/ask", json={"question": ""})
    assert resp.status_code == 400
    assert "No question" in resp.json()["error"]


@pytest.mark.asyncio
async def test_api_ask_no_api_key(client, test_db):
    db.save_daily_stats("2024-01-15", {"totalSteps": 8000})
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}, clear=False):
        resp = await client.post("/api/ask", json={"question": "How many steps?"})
    assert resp.status_code == 200
    assert "ANTHROPIC_API_KEY" in resp.json()["answer"]


@pytest.mark.asyncio
async def test_api_ask_with_mocked_llm(client, test_db):
    """Test the full ask flow with mocked Anthropic API."""
    db.save_daily_stats("2024-01-15", {"totalSteps": 8000})

    mock_sql_response = MagicMock()
    mock_sql_response.content = [
        MagicMock(
            text='{"sql": "SELECT date, json_extract(data, \'$.totalSteps\') as steps '
            'FROM daily_stats ORDER BY date DESC LIMIT 10", '
            '"explanation": "Last 10 days of steps"}'
        )
    ]

    mock_summary_response = MagicMock()
    mock_summary_response.content = [MagicMock(text="You averaged 8,000 steps. Great job!")]

    with (
        patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test-key"}),
        patch("garmin_tracker.llm_analyzer.anthropic.Anthropic") as mock_cls,
    ):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            mock_sql_response,
            mock_summary_response,
        ]
        mock_cls.return_value = mock_client

        resp = await client.post("/api/ask", json={"question": "How many steps did I walk?"})

    assert resp.status_code == 200
    assert "8,000 steps" in resp.json()["answer"]


@pytest.mark.asyncio
async def test_api_sync_mocked(client):
    """Test sync endpoint with mocked Garmin client."""
    mock_results = [{"date": "2024-01-15", "daily_stats": True, "activities": 0}]

    with patch("garmin_tracker.garmin_sync.sync_recent", return_value=mock_results):
        resp = await client.post("/api/sync", json={"days": 1})

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert len(data["results"]) == 1


@pytest.mark.asyncio
async def test_api_sync_failure(client):
    """Test sync endpoint when Garmin client fails."""
    with patch(
        "garmin_tracker.garmin_sync.sync_recent",
        side_effect=ValueError("GARMIN_EMAIL and GARMIN_PASSWORD must be set"),
    ):
        resp = await client.post("/api/sync", json={"days": 1})

    assert resp.status_code == 500
    assert "GARMIN_EMAIL" in resp.json()["message"]
