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

    def test_parse_block_datetime_returns_none_for_invalid_time(self) -> None:
        actual = gcal._parse_block_datetime(dt.date(2026, 1, 15), "25:61")
        self.assertIsNone(actual)

    def test_push_day_plan_skips_invalid_ranges_and_failed_creates(self) -> None:
        blocks = [
            {"start": "09:00", "end": "10:00", "title": "Valid"},
            {"start": "11:00", "end": "10:00", "title": "Backwards"},
            {"start": "bad", "end": "12:00", "title": "Broken"},
        ]

        with (
            mock.patch.object(gcal, "clear_life_os_events", return_value=0),
            mock.patch.object(gcal, "create_event", return_value="evt_123") as create_event,
        ):
            actual = gcal.push_day_plan(blocks, dt.date(2026, 1, 15))

        self.assertEqual(actual, ["evt_123"])
        self.assertEqual(create_event.call_count, 1)


if __name__ == "__main__":
    unittest.main()
