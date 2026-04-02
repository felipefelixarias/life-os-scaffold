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

    def test_parse_block_time_accepts_seconds_and_discards_them(self) -> None:
        actual = gcal._parse_block_time(dt.date(2026, 1, 15), "09:30:45", "start")
        expected = dt.datetime(2026, 1, 15, 9, 30)
        self.assertEqual(actual, expected)

    def test_parse_block_time_rejects_invalid_values(self) -> None:
        with self.assertRaises(ValueError):
            gcal._parse_block_time(dt.date(2026, 1, 15), "25:00", "start")


class GcalPlannerTests(unittest.TestCase):
    def test_clear_life_os_events_deletes_only_tagged_events(self) -> None:
        with (
            mock.patch.object(
                gcal,
                "get_agenda",
                return_value=[
                    {"id": "1", "description": f"note\n{gcal.LIFE_OS_TAG}"},
                    {"id": "2", "description": "plain event"},
                ],
            ),
            mock.patch.object(gcal, "delete_event") as delete_event,
        ):
            deleted = gcal.clear_life_os_events(dt.date(2026, 1, 15))

        self.assertEqual(deleted, 1)
        delete_event.assert_called_once_with("1", calendar_id="primary")

    def test_push_day_plan_skips_invalid_blocks_and_rolls_over_midnight(self) -> None:
        blocks = [
            {"start": "09:00", "end": "10:00", "title": "Focus", "domain": "work", "task_id": "T-1"},
            {"start": "23:30", "end": "00:15", "title": "Late wrap", "domain": "ops"},
            {"start": "nope", "end": "10:00", "title": "Broken"},
        ]

        with (
            mock.patch.object(gcal, "clear_life_os_events", return_value=0),
            mock.patch.object(gcal, "create_event", side_effect=["evt-1", "evt-2"]) as create_event,
        ):
            created = gcal.push_day_plan(blocks, dt.date(2026, 1, 15))

        self.assertEqual(created, ["evt-1", "evt-2"])
        self.assertEqual(create_event.call_count, 2)

        first_call = create_event.call_args_list[0].kwargs
        self.assertEqual(first_call["summary"], "[work] Focus")
        self.assertEqual(first_call["start_dt"], dt.datetime(2026, 1, 15, 9, 0))
        self.assertEqual(first_call["end_dt"], dt.datetime(2026, 1, 15, 10, 0))
        self.assertIn(gcal.LIFE_OS_TAG, first_call["description"])
        self.assertIn("Task: T-1", first_call["description"])

        second_call = create_event.call_args_list[1].kwargs
        self.assertEqual(second_call["summary"], "[ops] Late wrap")
        self.assertEqual(second_call["start_dt"], dt.datetime(2026, 1, 15, 23, 30))
        self.assertEqual(second_call["end_dt"], dt.datetime(2026, 1, 16, 0, 15))


if __name__ == "__main__":
    unittest.main()
