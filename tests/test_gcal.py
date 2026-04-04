import datetime as dt

# Mock Google API modules before importing gcal
import sys
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

mock_google = mock.MagicMock()
mock_google.auth.transport.requests.Request = mock.MagicMock()
mock_google.auth.exceptions.RefreshError = Exception
sys.modules["google"] = mock_google
sys.modules["google.auth"] = mock_google.auth
sys.modules["google.auth.transport"] = mock_google.auth.transport
sys.modules["google.auth.transport.requests"] = mock_google.auth.transport.requests
sys.modules["google.auth.exceptions"] = mock_google.auth.exceptions
sys.modules["googleapiclient"] = mock.MagicMock()
sys.modules["googleapiclient.discovery"] = mock.MagicMock()
sys.modules["googleapiclient.errors"] = mock.MagicMock()

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "01-ops" / "life-os" / "scripts" / "gcal.py"
)
SPEC = spec_from_file_location("life_os_gcal", MODULE_PATH)
gcal = module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(gcal)


class GcalCredentialsTests(unittest.TestCase):
    def setUp(self):
        self.token_path_patcher = mock.patch.object(gcal, "OAUTH_TOKEN_PATH")
        self.mock_token_path = self.token_path_patcher.start()
        self.addCleanup(self.token_path_patcher.stop)

    def test_get_credentials_raises_error_when_token_file_missing(self):
        self.mock_token_path.exists.return_value = False

        with self.assertRaises(FileNotFoundError) as cm:
            gcal.get_credentials()

        self.assertIn("OAuth token not found", str(cm.exception))

    def test_get_credentials_validates_file_location_security(self):
        self.mock_token_path.exists.return_value = True
        self.mock_token_path.resolve.return_value = Path("/tmp/malicious_token")

        with mock.patch("pathlib.Path.home", return_value=Path("/home/user")):
            with self.assertRaises(PermissionError) as cm:
                gcal.get_credentials()

        self.assertIn("outside user home directory", str(cm.exception))

    def test_get_credentials_warns_about_permissive_file_permissions(self):
        mock_stat = mock.Mock()
        mock_stat.st_mode = 0o666  # Too permissive
        mock_stat.st_size = 1024

        mock_resolved_path = mock.Mock()
        mock_resolved_path.stat.return_value = mock_stat
        mock_resolved_path.__str__ = mock.Mock(return_value="/home/user/.gcalcli_oauth")

        self.mock_token_path.exists.return_value = True
        self.mock_token_path.resolve.return_value = mock_resolved_path
        self.mock_token_path.stat.return_value = mock_stat

        mock_creds = mock.Mock()
        mock_creds.expired = False

        with (
            mock.patch("pathlib.Path.home", return_value=Path("/home/user")),
            mock.patch.object(gcal, "logger") as mock_logger,
            mock.patch("pickle.load", return_value=mock_creds),
            mock.patch("builtins.open", mock.mock_open()),
        ):
            gcal.get_credentials()

        mock_logger.warning.assert_called_once()
        warning_msg = mock_logger.warning.call_args[0][0]
        self.assertIn("overly permissive permissions", warning_msg)

    def test_get_credentials_rejects_oversized_token_file(self):
        mock_stat = mock.Mock()
        mock_stat.st_mode = 0o600
        mock_stat.st_size = gcal.MAX_OAUTH_TOKEN_SIZE + 1  # Too large

        mock_resolved_path = mock.Mock()
        mock_resolved_path.stat.return_value = mock_stat
        mock_resolved_path.__str__ = mock.Mock(return_value="/home/user/.gcalcli_oauth")

        self.mock_token_path.exists.return_value = True
        self.mock_token_path.resolve.return_value = mock_resolved_path
        self.mock_token_path.stat.return_value = mock_stat

        with mock.patch("pathlib.Path.home", return_value=Path("/home/user")):
            with self.assertRaises(PermissionError) as cm:
                gcal.get_credentials()

        self.assertIn("unexpectedly large", str(cm.exception))

    @mock.patch("pickle.load")
    @mock.patch("builtins.open", mock.mock_open())
    def test_get_credentials_refreshes_expired_credentials(self, mock_pickle_load):
        mock_stat = mock.Mock()
        mock_stat.st_mode = 0o600
        mock_stat.st_size = 1024

        mock_resolved_path = mock.Mock()
        mock_resolved_path.stat.return_value = mock_stat
        mock_resolved_path.__str__ = mock.Mock(return_value="/home/user/.gcalcli_oauth")

        mock_creds = mock.Mock()
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh_token"
        mock_pickle_load.return_value = mock_creds

        self.mock_token_path.exists.return_value = True
        self.mock_token_path.resolve.return_value = mock_resolved_path
        self.mock_token_path.stat.return_value = mock_stat
        self.mock_token_path.open = mock.mock_open()

        with (
            mock.patch("pathlib.Path.home", return_value=Path("/home/user")),
            mock.patch("google.auth.transport.requests.Request"),
            mock.patch("pickle.dump") as mock_pickle_dump,
        ):
            result = gcal.get_credentials()

        mock_creds.refresh.assert_called_once()
        mock_pickle_dump.assert_called_once_with(mock_creds, mock.ANY)
        self.assertEqual(result, mock_creds)


class GcalServiceTests(unittest.TestCase):
    def setUp(self):
        # Clear service cache before each test
        gcal._service_cache = None

    @mock.patch.object(gcal, "get_credentials")
    @mock.patch("googleapiclient.discovery.build")
    def test_get_service_creates_calendar_service(
        self, mock_build, mock_get_credentials
    ):
        mock_creds = mock.Mock()
        mock_get_credentials.return_value = mock_creds
        mock_service = mock.Mock()
        mock_build.return_value = mock_service

        result = gcal.get_service()

        mock_build.assert_called_once_with(
            "calendar", "v3", credentials=mock_creds, cache_discovery=False
        )
        self.assertEqual(result, mock_service)

    @mock.patch.object(gcal, "get_credentials")
    @mock.patch("googleapiclient.discovery.build")
    def test_get_service_caches_result(self, mock_build, mock_get_credentials):
        mock_service = mock.Mock()
        mock_build.return_value = mock_service

        # Clear any existing cache
        gcal._service_cache = None

        # Call twice
        result1 = gcal.get_service()
        result2 = gcal.get_service()

        # Should only build service once due to caching
        self.assertEqual(mock_build.call_count, 1)
        self.assertEqual(result1, result2)
        self.assertEqual(result1, mock_service)


class GcalCalendarOperationsTests(unittest.TestCase):
    def setUp(self):
        self.mock_service = mock.Mock()
        self.service_patcher = mock.patch.object(
            gcal, "get_service", return_value=self.mock_service
        )
        self.service_patcher.start()
        self.addCleanup(self.service_patcher.stop)

    def test_list_calendars_returns_calendar_list(self):
        expected_calendars = [
            {"id": "primary", "summary": "Primary Calendar"},
            {"id": "test@example.com", "summary": "Test Calendar"},
        ]

        mock_calendar_list = mock.Mock()
        mock_list_call = mock.Mock()
        mock_list_call.execute.return_value = {"items": expected_calendars}
        mock_calendar_list.list.return_value = mock_list_call
        self.mock_service.calendarList.return_value = mock_calendar_list

        result = gcal.list_calendars()

        self.assertEqual(result, expected_calendars)
        mock_calendar_list.list.assert_called_once()

    def test_get_agenda_retrieves_events_for_date_range(self):
        expected_events = [
            {"id": "event1", "summary": "Meeting 1"},
            {"id": "event2", "summary": "Meeting 2"},
        ]

        mock_events = mock.Mock()
        mock_list_call = mock.Mock()
        mock_list_call.execute.return_value = {"items": expected_events}
        mock_events.list.return_value = mock_list_call
        self.mock_service.events.return_value = mock_events

        start_date = dt.date(2026, 1, 15)
        end_date = dt.date(2026, 1, 16)

        result = gcal.get_agenda(start_date, end_date)

        self.assertEqual(result, expected_events)
        mock_events.list.assert_called_once()

    def test_create_event_builds_proper_event_structure(self):
        mock_events = mock.Mock()
        mock_insert_call = mock.Mock()
        mock_insert_call.execute.return_value = {"id": "new_event_id"}
        mock_events.insert.return_value = mock_insert_call
        self.mock_service.events.return_value = mock_events

        start_dt = dt.datetime(2026, 1, 15, 9, 0)
        end_dt = dt.datetime(2026, 1, 15, 10, 0)

        result = gcal.create_event(
            summary="Test Event",
            start_dt=start_dt,
            end_dt=end_dt,
            description="Test Description",
        )

        self.assertEqual(result, "new_event_id")

        # Verify the event structure passed to the API
        call_args = mock_events.insert.call_args
        event_body = call_args.kwargs["body"]

        self.assertEqual(event_body["summary"], "Test Event")
        self.assertEqual(event_body["description"], "Test Description")
        self.assertIn("dateTime", event_body["start"])
        self.assertIn("dateTime", event_body["end"])

    def test_delete_event_calls_api_with_correct_parameters(self):
        mock_events = mock.Mock()
        self.mock_service.events.return_value = mock_events

        gcal.delete_event("event_123", "calendar_456")

        mock_events.delete.assert_called_once_with(
            calendarId="calendar_456", eventId="event_123"
        )

    def test_search_events_filters_by_query(self):
        expected_events = [{"id": "found_event", "summary": "Found Event"}]

        mock_events = mock.Mock()
        mock_list_call = mock.Mock()
        mock_list_call.execute.return_value = {"items": expected_events}
        mock_events.list.return_value = mock_list_call
        self.mock_service.events.return_value = mock_events

        result = gcal.search_events(
            "meeting", dt.date(2026, 1, 15), dt.date(2026, 1, 16)
        )

        self.assertEqual(result, expected_events)

        # Verify search query was passed
        call_args = mock_events.list.call_args
        self.assertEqual(call_args.kwargs["q"], "meeting")


class GcalUtilityTests(unittest.TestCase):
    def test_format_event_line_formats_event_with_time(self):
        event = {
            "start": {"dateTime": "2026-01-15T09:00:00-08:00"},
            "end": {"dateTime": "2026-01-15T10:00:00-08:00"},
            "summary": "Test Meeting",
        }

        result = gcal.format_event_line(event)

        self.assertIn("Test Meeting", result)
        self.assertIn("09:00", result)
        self.assertIn("10:00", result)

    def test_format_event_line_handles_all_day_events(self):
        event = {"start": {"date": "2026-01-15"}, "summary": "All Day Event"}

        result = gcal.format_event_line(event)

        self.assertIn("All Day Event", result)
        self.assertIn("2026-01-15", result)

    def test_format_event_line_handles_missing_summary(self):
        event = {
            "start": {"dateTime": "2026-01-15T09:00:00-08:00"},
            "end": {"dateTime": "2026-01-15T10:00:00-08:00"},
        }

        result = gcal.format_event_line(event)

        self.assertIn("(no title)", result)


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
            {
                "start": "09:00",
                "end": "10:00",
                "title": "Focus",
                "domain": "work",
                "task_id": "T-1",
            },
            {"start": "23:30", "end": "00:15", "title": "Late wrap", "domain": "ops"},
            {"start": "nope", "end": "10:00", "title": "Broken"},
        ]

        with (
            mock.patch.object(gcal, "clear_life_os_events", return_value=0),
            mock.patch.object(
                gcal, "create_event", side_effect=["evt-1", "evt-2"]
            ) as create_event,
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
