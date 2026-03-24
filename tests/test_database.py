"""Tests for the database module."""

from garmin_tracker import database as db


class TestInitDb:
    def test_creates_tables(self, test_db):
        with db.get_db() as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            table_names = [t["name"] for t in tables]
        assert "daily_stats" in table_names
        assert "activities" in table_names
        assert "sleep" in table_names
        assert "heart_rate" in table_names
        assert "sync_log" in table_names


class TestSaveDailyStats:
    def test_insert_and_retrieve(self, test_db):
        db.save_daily_stats("2024-01-15", {"totalSteps": 8000, "totalKilocalories": 2200})
        with db.get_db() as conn:
            row = conn.execute("SELECT * FROM daily_stats WHERE date = '2024-01-15'").fetchone()
        assert row is not None
        assert row["date"] == "2024-01-15"

    def test_upsert_replaces(self, test_db):
        db.save_daily_stats("2024-01-15", {"totalSteps": 8000})
        db.save_daily_stats("2024-01-15", {"totalSteps": 9000})
        with db.get_db() as conn:
            count = conn.execute("SELECT COUNT(*) as c FROM daily_stats").fetchone()["c"]
        assert count == 1


class TestSaveActivity:
    def test_insert_activity(self, test_db):
        activity = {
            "activityId": 123,
            "startTimeLocal": "2024-01-15 08:00:00",
            "activityType": {"typeKey": "running"},
            "activityName": "Morning Run",
            "duration": 1800,
            "distance": 5000,
            "calories": 300,
            "averageHR": 145,
            "maxHR": 170,
        }
        db.save_activity(activity)
        with db.get_db() as conn:
            row = conn.execute("SELECT * FROM activities WHERE id = 123").fetchone()
        assert row["activity_type"] == "running"
        assert row["name"] == "Morning Run"


class TestSaveSleep:
    def test_insert_sleep(self, test_db):
        sleep_data = {
            "sleepTimeInSeconds": 28800,
            "deepSleepSeconds": 7200,
            "lightSleepSeconds": 14400,
            "remSleepSeconds": 5400,
            "awakeSleepSeconds": 1800,
        }
        db.save_sleep("2024-01-15", sleep_data)
        with db.get_db() as conn:
            row = conn.execute("SELECT * FROM sleep WHERE date = '2024-01-15'").fetchone()
        assert row["duration_seconds"] == 28800
        assert row["deep_seconds"] == 7200


class TestSaveHeartRate:
    def test_insert_heart_rate(self, test_db):
        hr_data = {"restingHeartRate": 58, "maxHeartRate": 165, "minHeartRate": 48}
        db.save_heart_rate("2024-01-15", hr_data)
        with db.get_db() as conn:
            row = conn.execute("SELECT * FROM heart_rate WHERE date = '2024-01-15'").fetchone()
        assert row["resting_hr"] == 58
        assert row["max_hr"] == 165
        assert row["min_hr"] == 48


class TestGetDateRange:
    def test_empty_db(self, test_db):
        min_date, max_date = db.get_date_range()
        assert min_date is None
        assert max_date is None

    def test_with_data(self, test_db):
        db.save_daily_stats("2024-01-10", {"totalSteps": 5000})
        db.save_daily_stats("2024-01-20", {"totalSteps": 8000})
        min_date, max_date = db.get_date_range()
        assert min_date == "2024-01-10"
        assert max_date == "2024-01-20"


class TestGetChartData:
    def test_steps_chart(self, test_db):
        db.save_daily_stats("2024-01-15", {"totalSteps": 8000})
        db.save_daily_stats("2024-01-16", {"totalSteps": 10000})
        data = db.get_chart_data("steps", days=30)
        assert len(data) == 2
        assert data[0]["value"] == 8000
        assert data[1]["value"] == 10000

    def test_unknown_metric_returns_empty(self, test_db):
        data = db.get_chart_data("unknown_metric", days=30)
        assert data == []

    def test_sleep_chart(self, test_db):
        db.save_sleep(
            "2024-01-15",
            {
                "sleepTimeInSeconds": 28800,
                "deepSleepSeconds": 7200,
                "lightSleepSeconds": 14400,
                "remSleepSeconds": 5400,
                "awakeSleepSeconds": 1800,
            },
        )
        data = db.get_chart_data("sleep", days=30)
        assert len(data) == 1
        assert data[0]["value"] == 8.0  # 28800 / 3600


class TestGetDataSummary:
    def test_empty_db(self, test_db):
        summary = db.get_data_summary(days=30)
        assert "HEALTH DATA SUMMARY" in summary

    def test_with_data(self, test_db):
        db.save_daily_stats("2024-01-15", {"totalSteps": 8000, "totalKilocalories": 2200})
        db.save_heart_rate(
            "2024-01-15",
            {"restingHeartRate": 58, "maxHeartRate": 165, "minHeartRate": 48},
        )
        summary = db.get_data_summary(days=30)
        assert "8000" in summary
        assert "resting=58" in summary
