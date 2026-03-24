"""Shared test fixtures."""

from unittest.mock import patch

import pytest

from garmin_tracker import database as db


@pytest.fixture()
def test_db(tmp_path):
    """Provide an isolated in-memory-like SQLite database for tests."""
    test_db_path = tmp_path / "test.db"
    with patch.object(db, "DB_PATH", test_db_path):
        db.init_db()
        yield test_db_path
