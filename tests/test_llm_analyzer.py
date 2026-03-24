"""Tests for the LLM analyzer module (pure functions only, no API calls)."""

from garmin_tracker.llm_analyzer import _format_results


class TestFormatResults:
    def test_empty_results(self):
        assert _format_results([], []) == "(No results)"

    def test_single_row(self):
        rows = [{"date": "2024-01-15", "steps": 8000}]
        columns = ["date", "steps"]
        result = _format_results(rows, columns)
        assert "2024-01-15" in result
        assert "8000" in result
        assert "| date | steps |" in result

    def test_truncation(self):
        rows = [{"v": i} for i in range(100)]
        columns = ["v"]
        result = _format_results(rows, columns, max_rows=10)
        assert "100 total rows" in result
        assert "showing first 10" in result

    def test_no_truncation_when_under_limit(self):
        rows = [{"v": i} for i in range(5)]
        columns = ["v"]
        result = _format_results(rows, columns, max_rows=50)
        assert "total rows" not in result
