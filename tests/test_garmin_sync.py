"""Tests for garmin_sync module with mocked Garmin client."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from garmin_tracker import database as db
from garmin_tracker import garmin_sync as sync


class TestGetClient:
    def test_raises_without_credentials(self):
        sync._client = None
        with (
            patch.dict("os.environ", {"GARMIN_EMAIL": "", "GARMIN_PASSWORD": ""}),
            pytest.raises(ValueError, match="GARMIN_EMAIL"),
        ):
            sync.get_client()
        sync._client = None

    def test_caches_client(self):
        mock_garmin = MagicMock()
        sync._client = mock_garmin
        assert sync.get_client() is mock_garmin
        sync._client = None


class TestSyncDate:
    def test_syncs_all_data_types(self, test_db):
        mock_client = MagicMock()
        mock_client.get_stats.return_value = {"totalSteps": 8000}
        mock_client.get_activities_by_date.return_value = [
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
        ]
        mock_client.get_sleep_data.return_value = {
            "dailySleepDTO": {
                "sleepTimeInSeconds": 28800,
                "deepSleepSeconds": 7200,
                "lightSleepSeconds": 14400,
                "remSleepSeconds": 5400,
                "awakeSleepSeconds": 1800,
            }
        }
        mock_client.get_heart_rates.return_value = {
            "restingHeartRate": 58,
            "maxHeartRate": 165,
            "minHeartRate": 48,
        }

        with (
            patch.object(sync, "get_client", return_value=mock_client),
            patch("garmin_tracker.garmin_sync.time.sleep"),
        ):
            result = sync.sync_date(date(2024, 1, 15))

        assert result["daily_stats"] is True
        assert result["activities"] == 1
        assert result["sleep"] is True
        assert result["heart_rate"] is True

        # Verify data was saved
        with db.get_db() as conn:
            stats = conn.execute("SELECT * FROM daily_stats").fetchall()
            assert len(stats) == 1
            acts = conn.execute("SELECT * FROM activities").fetchall()
            assert len(acts) == 1

    def test_handles_api_errors_gracefully(self, test_db):
        mock_client = MagicMock()
        mock_client.get_stats.side_effect = Exception("API error")
        mock_client.get_activities_by_date.side_effect = Exception("API error")
        mock_client.get_sleep_data.side_effect = Exception("API error")
        mock_client.get_heart_rates.side_effect = Exception("API error")

        with (
            patch.object(sync, "get_client", return_value=mock_client),
            patch("garmin_tracker.garmin_sync.time.sleep"),
        ):
            result = sync.sync_date(date(2024, 1, 15))

        assert result["daily_stats"] == "API error"
        assert result["activities"] == "API error"
        assert result["sleep"] == "API error"
        assert result["heart_rate"] == "API error"


class TestSyncRecent:
    def test_syncs_multiple_days(self, test_db):
        mock_client = MagicMock()
        mock_client.get_stats.return_value = {"totalSteps": 5000}
        mock_client.get_activities_by_date.return_value = []
        mock_client.get_sleep_data.return_value = None
        mock_client.get_heart_rates.return_value = None

        with (
            patch.object(sync, "get_client", return_value=mock_client),
            patch("garmin_tracker.garmin_sync.time.sleep"),
        ):
            results = sync.sync_recent(days=3)

        assert len(results) == 3
        assert all(r["daily_stats"] is True for r in results)
