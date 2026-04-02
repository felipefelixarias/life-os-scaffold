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

    def test_search_events_logs_shared_api_errors(self) -> None:
        with mock.patch.object(gcal, "_load_timezone", return_value="America/Los_Angeles"):
            with mock.patch.object(gcal, "_rfc3339", side_effect=["2026-01-15T00:00:00-08:00", "2026-01-16T00:00:00-08:00"]):
                with mock.patch.object(gcal, "get_service", side_effect=RuntimeError("boom")):
                    with mock.patch.object(gcal, "_log_google_api_error") as log_mock:
                        actual = gcal.search_events(
                            "planning",
                            dt.date(2026, 1, 15),
                            dt.date(2026, 1, 16),
                        )

        self.assertEqual(actual, [])
        log_mock.assert_called_once()
        self.assertEqual(log_mock.call_args[0][0], "searching events for 'planning'")

    def test_delete_event_logs_delete_specific_errors(self) -> None:
        fake_service = mock.Mock()
        fake_service.events.return_value.delete.return_value.execute.side_effect = RuntimeError("boom")

        with mock.patch.object(gcal, "get_service", return_value=fake_service):
            with mock.patch.object(gcal, "_log_delete_event_error") as log_mock:
                gcal.delete_event("evt-123")

        log_mock.assert_called_once()
        self.assertEqual(log_mock.call_args[0][0], "evt-123")


if __name__ == "__main__":
    unittest.main()
