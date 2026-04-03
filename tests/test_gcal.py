import datetime as dt
import unittest
from unittest import mock

from zoneinfo import ZoneInfo

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "01-ops" / "life-os" / "scripts" / "gcal.py"
)
SPEC = spec_from_file_location("life_os_gcal", MODULE_PATH)
assert SPEC is not None
gcal = module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(gcal)


class GcalTimezoneTests(unittest.TestCase):
    def test_rfc3339_uses_zoneinfo_for_non_us_timezone(self) -> None:
        with mock.patch.object(gcal, "_load_timezone", return_value="Europe/Paris"):
            actual = gcal._rfc3339(dt.date(2026, 1, 15), "09:30:00")
        expected = dt.datetime(
            2026, 1, 15, 9, 30, 0, tzinfo=ZoneInfo("Europe/Paris")
        ).isoformat()
        self.assertEqual(actual, expected)

    def test_invalid_timezone_falls_back_to_default(self) -> None:
        fallback = gcal._get_zoneinfo("Mars/Olympus_Mons")
        self.assertEqual(str(fallback), "America/Los_Angeles")

    def test_rfc3339_handles_invalid_time_format(self) -> None:
        """Test that invalid time formats fallback to 00:00:00."""
        with mock.patch.object(gcal, "_load_timezone", return_value="UTC"):
            # Invalid time format should fallback to 00:00:00
            result = gcal._rfc3339(dt.date(2026, 1, 15), "invalid")
            expected = dt.datetime(2026, 1, 15, 0, 0, 0, tzinfo=ZoneInfo("UTC")).isoformat()
            self.assertEqual(result, expected)

    def test_rfc3339_validates_hour_range(self) -> None:
        """Test that invalid hours fallback to 00:00:00."""
        with mock.patch.object(gcal, "_load_timezone", return_value="UTC"):
            result = gcal._rfc3339(dt.date(2026, 1, 15), "25:30:00")
            expected = dt.datetime(2026, 1, 15, 0, 0, 0, tzinfo=ZoneInfo("UTC")).isoformat()
            self.assertEqual(result, expected)

    def test_validate_time_block_with_valid_data(self) -> None:
        """Test _validate_time_block with valid input."""
        block = {
            "start": "09:00",
            "end": "10:30",
            "title": "Test Meeting",
            "domain": "work",
            "task_id": "task-123"
        }
        result = gcal._validate_time_block(block)

        self.assertIsNotNone(result)
        self.assertEqual(result["start_hour"], 9)
        self.assertEqual(result["start_min"], 0)
        self.assertEqual(result["end_hour"], 10)
        self.assertEqual(result["end_min"], 30)
        self.assertEqual(result["title"], "Test Meeting")

    def test_validate_time_block_with_invalid_time(self) -> None:
        """Test _validate_time_block with invalid time format."""
        block = {
            "start": "invalid",
            "end": "10:30",
            "title": "Test Meeting"
        }
        result = gcal._validate_time_block(block)
        self.assertIsNone(result)

    def test_validate_time_block_missing_required_fields(self) -> None:
        """Test _validate_time_block with missing required fields."""
        block = {
            "start": "09:00",
            # Missing "end" field
            "title": "Test Meeting"
        }
        result = gcal._validate_time_block(block)
        self.assertIsNone(result)

    def test_format_event_line_with_complete_event(self) -> None:
        """Test format_event_line with a complete event."""
        event = {
            "summary": "Test Meeting",
            "start": {"dateTime": "2026-01-15T09:00:00-08:00"},
            "end": {"dateTime": "2026-01-15T10:30:00-08:00"},
            "location": "Conference Room A"
        }
        result = gcal.format_event_line(event)
        self.assertIn("09:00 - 10:30", result)
        self.assertIn("Test Meeting", result)
        self.assertIn("Conference Room A", result)


if __name__ == "__main__":
    unittest.main()
