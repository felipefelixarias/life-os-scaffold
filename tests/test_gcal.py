from __future__ import annotations

import datetime as dt

# Mock Google API modules before importing gcal
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

import pytest

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


class TestGcalCredentials:
    def setup_method(self):
        self._token_path_patcher = mock.patch.object(gcal, "OAUTH_TOKEN_PATH")
        self.mock_token_path = self._token_path_patcher.start()

    def teardown_method(self):
        self._token_path_patcher.stop()

    def test_get_credentials_raises_error_when_token_file_missing(self):
        self.mock_token_path.exists.return_value = False

        with pytest.raises(FileNotFoundError) as cm:
            gcal.get_credentials()

        assert "OAuth token not found" in str(cm.value)

    def test_get_credentials_validates_file_location_security(self):
        self.mock_token_path.exists.return_value = True
        self.mock_token_path.resolve.return_value = Path("/tmp/malicious_token")  # nosec B108

        with (
            mock.patch("pathlib.Path.home", return_value=Path("/home/user")),
            pytest.raises(PermissionError) as cm,
        ):
            gcal.get_credentials()

        assert "outside user home directory" in str(cm.value)

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
        assert "overly permissive permissions" in warning_msg

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

        with (
            mock.patch("pathlib.Path.home", return_value=Path("/home/user")),
            pytest.raises(PermissionError) as cm,
        ):
            gcal.get_credentials()

        assert "unexpectedly large" in str(cm.value)

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
        mock_creds.refresh_token = "refresh_token"  # nosec B105
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
        assert result == mock_creds


class TestGcalService:
    def setup_method(self):
        # Clear service cache before each test
        gcal._service_cache = None

    @mock.patch.object(gcal, "get_credentials")
    @mock.patch("googleapiclient.discovery.build")
    def test_get_service_creates_calendar_service(
        self, mock_build, mock_get_credentials,
    ):
        mock_creds = mock.Mock()
        mock_get_credentials.return_value = mock_creds
        mock_service = mock.Mock()
        mock_build.return_value = mock_service

        result = gcal.get_service()

        mock_build.assert_called_once_with(
            "calendar", "v3", credentials=mock_creds, cache_discovery=False,
        )
        assert result == mock_service

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
        assert mock_build.call_count == 1
        assert result1 == result2
        assert result1 == mock_service


class TestGcalCalendarOperations:
    def setup_method(self):
        self.mock_service = mock.Mock()
        self._service_patcher = mock.patch.object(
            gcal, "get_service", return_value=self.mock_service,
        )
        self._service_patcher.start()

    def teardown_method(self):
        self._service_patcher.stop()

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

        assert result == expected_calendars
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

        assert result == expected_events
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

        assert result == "new_event_id"

        # Verify the event structure passed to the API
        call_args = mock_events.insert.call_args
        event_body = call_args.kwargs["body"]

        assert event_body["summary"] == "Test Event"
        assert event_body["description"] == "Test Description"
        assert "dateTime" in event_body["start"]
        assert "dateTime" in event_body["end"]

    def test_delete_event_calls_api_with_correct_parameters(self):
        mock_events = mock.Mock()
        self.mock_service.events.return_value = mock_events

        gcal.delete_event("event_123", "calendar_456")

        mock_events.delete.assert_called_once_with(
            calendarId="calendar_456", eventId="event_123",
        )

    def test_search_events_filters_by_query(self):
        expected_events = [{"id": "found_event", "summary": "Found Event"}]

        mock_events = mock.Mock()
        mock_list_call = mock.Mock()
        mock_list_call.execute.return_value = {"items": expected_events}
        mock_events.list.return_value = mock_list_call
        self.mock_service.events.return_value = mock_events

        result = gcal.search_events(
            "meeting", dt.date(2026, 1, 15), dt.date(2026, 1, 16),
        )

        assert result == expected_events

        # Verify search query was passed
        call_args = mock_events.list.call_args
        assert call_args.kwargs["q"] == "meeting"


class TestGcalUtility:
    def test_format_event_line_formats_event_with_time(self):
        event = {
            "start": {"dateTime": "2026-01-15T09:00:00-08:00"},
            "end": {"dateTime": "2026-01-15T10:00:00-08:00"},
            "summary": "Test Meeting",
        }

        result = gcal.format_event_line(event)

        assert "Test Meeting" in result
        assert "09:00" in result
        assert "10:00" in result

    def test_format_event_line_handles_all_day_events(self):
        event = {"start": {"date": "2026-01-15"}, "summary": "All Day Event"}

        result = gcal.format_event_line(event)

        assert "All Day Event" in result
        assert "2026-01-15" in result

    def test_format_event_line_handles_missing_summary(self):
        event = {
            "start": {"dateTime": "2026-01-15T09:00:00-08:00"},
            "end": {"dateTime": "2026-01-15T10:00:00-08:00"},
        }

        result = gcal.format_event_line(event)

        assert "(no title)" in result


class TestGcalTimezone:
    def test_rfc3339_uses_zoneinfo_for_non_us_timezone(self) -> None:
        with mock.patch.object(gcal, "_load_timezone", return_value="Europe/Paris"):
            actual = gcal._rfc3339(dt.date(2026, 1, 15), "09:30:00")
        expected = dt.datetime(
            2026, 1, 15, 9, 30, 0, tzinfo=ZoneInfo("Europe/Paris"),
        ).isoformat()
        assert actual == expected

    def test_invalid_timezone_falls_back_to_default(self) -> None:
        fallback = gcal._get_zoneinfo("Mars/Olympus_Mons")
        assert str(fallback) == "America/Los_Angeles"

    def test_parse_block_time_accepts_seconds_and_discards_them(self) -> None:
        actual = gcal._parse_block_time(dt.date(2026, 1, 15), "09:30:45", "start")
        expected = dt.datetime(2026, 1, 15, 9, 30)
        assert actual == expected

    def test_parse_block_time_rejects_invalid_values(self) -> None:
        with pytest.raises(ValueError, match=r"invalid start time '25:00'"):
            gcal._parse_block_time(dt.date(2026, 1, 15), "25:00", "start")


class TestGcalErrorHandling:
    """Tests for error-handling branches in gcal functions."""

    def setup_method(self):
        self.mock_service = mock.Mock()
        self._service_patcher = mock.patch.object(
            gcal, "get_service", return_value=self.mock_service,
        )
        self._service_patcher.start()

    def teardown_method(self):
        self._service_patcher.stop()

    def test_list_calendars_returns_empty_on_auth_error(self):
        with mock.patch.object(gcal, "get_service", side_effect=FileNotFoundError):
            result = gcal.list_calendars()
        assert result == []

    def test_list_calendars_returns_empty_on_generic_error(self):
        with mock.patch.object(gcal, "get_service", side_effect=RuntimeError("API down")), \
             mock.patch.object(gcal, "_log_google_api_error"):
            result = gcal.list_calendars()
        assert result == []

    def test_get_agenda_returns_empty_on_auth_error(self):
        with mock.patch.object(gcal, "get_service", side_effect=PermissionError):
            result = gcal.get_agenda(dt.date(2026, 1, 15))
        assert result == []

    def test_get_agenda_returns_empty_on_generic_error(self):
        with mock.patch.object(gcal, "get_service", side_effect=RuntimeError("boom")), \
             mock.patch.object(gcal, "_log_google_api_error"):
            result = gcal.get_agenda(dt.date(2026, 1, 15), dt.date(2026, 1, 16))
        assert result == []

    def test_get_agenda_defaults_end_date_when_none(self):
        mock_events = mock.Mock()
        mock_list_call = mock.Mock()
        mock_list_call.execute.return_value = {"items": [{"id": "e1"}]}
        mock_events.list.return_value = mock_list_call
        self.mock_service.events.return_value = mock_events

        result = gcal.get_agenda(dt.date(2026, 1, 15))
        assert result == [{"id": "e1"}]

    def test_get_agenda_handles_pagination(self):
        mock_events = mock.Mock()
        page1 = mock.Mock()
        page1.execute.return_value = {
            "items": [{"id": "e1"}],
            "nextPageToken": "token2",
        }
        page2 = mock.Mock()
        page2.execute.return_value = {"items": [{"id": "e2"}]}
        mock_events.list.return_value = mock.Mock(
            execute=mock.Mock(side_effect=[page1.execute(), page2.execute()]),
        )
        # Need to handle multiple calls
        call_count = [0]
        def mock_list(**kwargs):
            m = mock.Mock()
            if call_count[0] == 0:
                m.execute.return_value = {
                    "items": [{"id": "e1"}],
                    "nextPageToken": "token2",
                }
            else:
                m.execute.return_value = {"items": [{"id": "e2"}]}
            call_count[0] += 1
            return m
        mock_events.list.side_effect = mock_list
        self.mock_service.events.return_value = mock_events

        result = gcal.get_agenda(dt.date(2026, 1, 15), dt.date(2026, 1, 16))
        assert len(result) == 2
        assert result[0]["id"] == "e1"
        assert result[1]["id"] == "e2"

    def test_create_event_returns_empty_on_auth_error(self):
        with mock.patch.object(gcal, "get_service", side_effect=FileNotFoundError):
            result = gcal.create_event(
                "Test", dt.datetime(2026, 1, 15, 9), dt.datetime(2026, 1, 15, 10),
            )
        assert result == ""

    def test_create_event_returns_empty_on_value_error(self):
        with mock.patch.object(gcal, "get_service", side_effect=ValueError("bad")):
            result = gcal.create_event(
                "Test", dt.datetime(2026, 1, 15, 9), dt.datetime(2026, 1, 15, 10),
            )
        assert result == ""

    def test_create_event_returns_empty_on_generic_error(self):
        with mock.patch.object(gcal, "get_service", side_effect=RuntimeError("fail")), \
             mock.patch.object(gcal, "_log_google_api_error"):
            result = gcal.create_event(
                "Test", dt.datetime(2026, 1, 15, 9), dt.datetime(2026, 1, 15, 10),
            )
        assert result == ""

    def test_create_event_includes_location_and_reminders(self):
        mock_events = mock.Mock()
        mock_insert = mock.Mock()
        mock_insert.execute.return_value = {"id": "loc_event"}
        mock_events.insert.return_value = mock_insert
        self.mock_service.events.return_value = mock_events

        result = gcal.create_event(
            summary="Located Event",
            start_dt=dt.datetime(2026, 1, 15, 9),
            end_dt=dt.datetime(2026, 1, 15, 10),
            location="Room 101",
            reminders={"useDefault": False},
        )
        assert result == "loc_event"
        body = mock_events.insert.call_args.kwargs["body"]
        assert body["location"] == "Room 101"
        assert body["reminders"] == {"useDefault": False}

    def test_update_event_returns_updated_event(self):
        mock_events = mock.Mock()
        existing = {"id": "e1", "summary": "Old"}
        mock_get = mock.Mock()
        mock_get.execute.return_value = existing
        mock_events.get.return_value = mock_get
        mock_update = mock.Mock()
        mock_update.execute.return_value = {"id": "e1", "summary": "New"}
        mock_events.update.return_value = mock_update
        self.mock_service.events.return_value = mock_events

        result = gcal.update_event("e1", summary="New")
        assert result["summary"] == "New"

    def test_update_event_handles_datetime_kwargs(self):
        mock_events = mock.Mock()
        existing = {"id": "e1", "summary": "Event"}
        mock_get = mock.Mock()
        mock_get.execute.return_value = existing
        mock_events.get.return_value = mock_get
        mock_update = mock.Mock()
        mock_update.execute.return_value = existing
        mock_events.update.return_value = mock_update
        self.mock_service.events.return_value = mock_events

        new_start = dt.datetime(2026, 1, 15, 14, 0)
        gcal.update_event("e1", start=new_start)

        call_body = mock_events.update.call_args.kwargs["body"]
        assert "dateTime" in call_body["start"]

    def test_update_event_returns_empty_on_auth_error(self):
        with mock.patch.object(gcal, "get_service", side_effect=PermissionError):
            result = gcal.update_event("e1", summary="X")
        assert result == {}

    def test_update_event_returns_empty_on_value_error(self):
        with mock.patch.object(gcal, "get_service", side_effect=ValueError("bad")):
            result = gcal.update_event("e1", summary="X")
        assert result == {}

    def test_update_event_returns_empty_on_generic_error(self):
        with mock.patch.object(gcal, "get_service", side_effect=RuntimeError("fail")), \
             mock.patch.object(gcal, "_log_google_api_error"):
            result = gcal.update_event("e1", summary="X")
        assert result == {}

    def test_delete_event_handles_auth_error(self):
        with mock.patch.object(gcal, "get_service", side_effect=FileNotFoundError):
            gcal.delete_event("e1")  # Should not raise

    def test_delete_event_handles_generic_error(self):
        mock_events = mock.Mock()
        mock_events.delete.return_value.execute.side_effect = RuntimeError("fail")
        self.mock_service.events.return_value = mock_events
        with mock.patch.object(gcal, "_is_http_error_status", return_value=False), \
             mock.patch.object(gcal, "_log_google_api_error"):
            gcal.delete_event("e1")  # Should not raise

    def test_search_events_returns_empty_on_auth_error(self):
        with mock.patch.object(gcal, "get_service", side_effect=FileNotFoundError):
            result = gcal.search_events(
                "test", dt.date(2026, 1, 15), dt.date(2026, 1, 16),
            )
        assert result == []

    def test_search_events_returns_empty_on_generic_error(self):
        with mock.patch.object(gcal, "get_service", side_effect=RuntimeError("fail")), \
             mock.patch.object(gcal, "_log_google_api_error"):
            result = gcal.search_events(
                "test", dt.date(2026, 1, 15), dt.date(2026, 1, 16),
            )
        assert result == []

    def test_rfc3339_handles_invalid_time_format(self):
        with mock.patch.object(gcal, "_load_timezone", return_value="UTC"):
            result = gcal._rfc3339(dt.date(2026, 1, 15), "not-a-time")
        # Should fallback to 00:00:00
        assert "2026-01-15T00:00:00" in result

    def test_log_google_api_error_handles_import_error(self):
        with mock.patch.dict("sys.modules", {"googleapiclient.errors": None}), \
             mock.patch.object(gcal, "logger") as mock_logger:
            gcal._log_google_api_error("testing", RuntimeError("boom"))
        mock_logger.error.assert_called_once()
        assert "Unexpected error" in mock_logger.error.call_args[0][0]

    def test_is_http_error_status_handles_import_error(self):
        with mock.patch.dict("sys.modules", {"googleapiclient.errors": None}):
            result = gcal._is_http_error_status(RuntimeError("boom"), 404)
        assert result is False

    def test_load_timezone_caches_result(self):
        gcal._timezone_cache = None
        with mock.patch.object(gcal, "PROFILE_PATH") as mock_path:
            mock_path.open = mock.mock_open(read_data='{"timezone": "Europe/London"}')
            tz1 = gcal._load_timezone()
            tz2 = gcal._load_timezone()
        assert tz1 == "Europe/London"
        assert tz1 == tz2
        # Reset for other tests
        gcal._timezone_cache = None

    def test_load_timezone_handles_missing_file(self):
        gcal._timezone_cache = None
        with mock.patch.object(gcal, "PROFILE_PATH") as mock_path:
            mock_path.open.side_effect = FileNotFoundError
            tz = gcal._load_timezone()
        assert tz == "America/Los_Angeles"
        gcal._timezone_cache = None

    def test_get_credentials_handles_os_error_during_validation(self):
        with mock.patch.object(gcal, "OAUTH_TOKEN_PATH") as mock_path:
            mock_path.exists.return_value = True
            mock_path.resolve.side_effect = OSError("cannot resolve")
            with pytest.raises(PermissionError, match="Cannot validate"):
                gcal.get_credentials()


class TestGcalPushDayPlanEdgeCases:
    """Tests for push_day_plan edge cases and logging paths."""

    def test_push_day_plan_logs_cleared_events(self):
        blocks = [
            {"start": "09:00", "end": "10:00", "title": "Work"},
        ]
        with (
            mock.patch.object(gcal, "clear_life_os_events", return_value=3),
            mock.patch.object(gcal, "create_event", return_value="evt-1"),
            mock.patch.object(gcal, "logger") as mock_logger,
        ):
            gcal.push_day_plan(blocks, dt.date(2026, 1, 15))
        # Should log that 3 events were cleared
        info_calls = [str(c) for c in mock_logger.info.call_args_list]
        assert any("3" in c for c in info_calls)

    def test_push_day_plan_logs_failed_blocks(self):
        blocks = [
            {"start": "09:00", "end": "10:00", "title": "Work"},
        ]
        with (
            mock.patch.object(gcal, "clear_life_os_events", return_value=0),
            mock.patch.object(gcal, "create_event", return_value=""),  # fails
            mock.patch.object(gcal, "logger") as mock_logger,
        ):
            result = gcal.push_day_plan(blocks, dt.date(2026, 1, 15))
        assert result == []
        mock_logger.error.assert_called_once()
        assert "failed" in mock_logger.error.call_args[0][0]

    def test_push_day_plan_block_without_domain(self):
        blocks = [
            {"start": "09:00", "end": "10:00", "title": "No Domain Block"},
        ]
        with (
            mock.patch.object(gcal, "clear_life_os_events", return_value=0),
            mock.patch.object(gcal, "create_event", return_value="evt-1") as mock_create,
        ):
            gcal.push_day_plan(blocks, dt.date(2026, 1, 15))
        # Summary should be just the title, no domain prefix
        assert mock_create.call_args.kwargs["summary"] == "No Domain Block"

    def test_format_event_line_with_location(self):
        event = {
            "start": {"dateTime": "2026-01-15T09:00:00-08:00"},
            "end": {"dateTime": "2026-01-15T10:00:00-08:00"},
            "summary": "Meeting",
            "location": "Room 42",
        }
        result = gcal.format_event_line(event)
        assert "(Room 42)" in result


class TestGcalPlanner:
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

        assert deleted == 1
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
                gcal, "create_event", side_effect=["evt-1", "evt-2"],
            ) as create_event,
        ):
            created = gcal.push_day_plan(blocks, dt.date(2026, 1, 15))

        assert created == ["evt-1", "evt-2"]
        assert create_event.call_count == 2

        first_call = create_event.call_args_list[0].kwargs
        assert first_call["summary"] == "[work] Focus"
        assert first_call["start_dt"] == dt.datetime(2026, 1, 15, 9, 0)
        assert first_call["end_dt"] == dt.datetime(2026, 1, 15, 10, 0)
        assert gcal.LIFE_OS_TAG in first_call["description"]
        assert "Task: T-1" in first_call["description"]

        second_call = create_event.call_args_list[1].kwargs
        assert second_call["summary"] == "[ops] Late wrap"
        assert second_call["start_dt"] == dt.datetime(2026, 1, 15, 23, 30)
        assert second_call["end_dt"] == dt.datetime(2026, 1, 16, 0, 15)
