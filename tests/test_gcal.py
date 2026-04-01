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

    def test_rfc3339_with_invalid_time_uses_default(self) -> None:
        with mock.patch.object(gcal, "_load_timezone", return_value="UTC"):
            actual = gcal._rfc3339(dt.date(2026, 1, 15), "25:99:99")
        expected = dt.datetime(
            2026, 1, 15, 0, 0, 0, tzinfo=ZoneInfo("UTC")
        ).isoformat()
        self.assertEqual(actual, expected)

    def test_rfc3339_with_default_time(self) -> None:
        with mock.patch.object(gcal, "_load_timezone", return_value="UTC"):
            actual = gcal._rfc3339(dt.date(2026, 1, 15))
        expected = dt.datetime(
            2026, 1, 15, 0, 0, 0, tzinfo=ZoneInfo("UTC")
        ).isoformat()
        self.assertEqual(actual, expected)

    def test_handle_api_exception_with_file_not_found(self) -> None:
        with mock.patch.object(gcal.logger, 'error') as mock_error:
            result = gcal._handle_api_exception(FileNotFoundError("test"), "testing", [])
            mock_error.assert_called_once_with("Authentication error while testing: test")
            self.assertEqual(result, [])

    def test_handle_api_exception_with_generic_exception(self) -> None:
        with mock.patch.object(gcal.logger, 'error') as mock_error:
            result = gcal._handle_api_exception(ValueError("test"), "testing", "default")
            # The exact message depends on whether googleapiclient.errors can be imported
            self.assertTrue(
                mock_error.called and
                any("testing: test" in str(call) for call in mock_error.call_args_list)
            )
            self.assertEqual(result, "default")


class TimeFormatValidationTests(unittest.TestCase):
    def test_time_format_pattern_valid_times(self) -> None:
        valid_times = ["00:00", "12:30", "23:59", "9:15", "01:01"]
        for time_str in valid_times:
            with self.subTest(time_str=time_str):
                self.assertTrue(gcal.TIME_FORMAT_PATTERN.match(time_str))

    def test_time_format_pattern_invalid_times(self) -> None:
        invalid_times = ["24:00", "12:60", "99:99", "1:1", "ab:cd", "12", "12:"]
        for time_str in invalid_times:
            with self.subTest(time_str=time_str):
                self.assertFalse(gcal.TIME_FORMAT_PATTERN.match(time_str))


if __name__ == "__main__":
    unittest.main()
