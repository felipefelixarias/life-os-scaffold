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

    def test_push_day_plan_skips_invalid_blocks_and_normalizes_seconds(self) -> None:
        blocks = [
            {"start": "09:00", "end": "10:00", "title": "Deep Work", "domain": "career"},
            {"start": "bad", "end": "11:00", "title": "Broken Block"},
            {"start": "11:00:30", "end": "12:00:15", "title": "With Seconds"},
        ]

        with (
            mock.patch.object(gcal, "clear_life_os_events", return_value=0),
            mock.patch.object(gcal, "create_event", side_effect=["evt-1", "evt-3"]) as create_event,
        ):
            created = gcal.push_day_plan(blocks, dt.date(2026, 1, 15))

        self.assertEqual(created, ["evt-1", "evt-3"])
        self.assertEqual(create_event.call_count, 2)

        first_call = create_event.call_args_list[0].kwargs
        self.assertEqual(first_call["summary"], "[career] Deep Work")

        second_call = create_event.call_args_list[1].kwargs
        self.assertEqual(second_call["start_dt"], dt.datetime(2026, 1, 15, 11, 0))
        self.assertEqual(second_call["end_dt"], dt.datetime(2026, 1, 15, 12, 0))

    def test_push_day_plan_skips_failed_event_creations(self) -> None:
        blocks = [
            {"start": "09:00", "end": "10:00", "title": "Deep Work"},
            {"start": "10:30", "end": "11:00", "title": "Review"},
        ]

        with (
            mock.patch.object(gcal, "clear_life_os_events", return_value=0),
            mock.patch.object(gcal, "create_event", side_effect=["evt-1", ""]),
        ):
            created = gcal.push_day_plan(blocks, dt.date(2026, 1, 15))

        self.assertEqual(created, ["evt-1"])


if __name__ == "__main__":
    unittest.main()
