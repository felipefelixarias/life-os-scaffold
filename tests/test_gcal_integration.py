"""Integration tests for the Google Calendar API wrapper (``gcal.py``).

These tests exercise ``gcal.py`` against the real Google Calendar API.
They are **opt-in** and auto-skipped in CI to prevent accidental runs:

Required to enable:
    LIFE_OS_GCAL_INTEGRATION=1
        Explicit opt-in flag.
    LIFE_OS_GCAL_TEST_CALENDAR_ID=<calendar id>
        ID of a **dedicated test calendar** (NOT your primary calendar).
        Example: ``abcd1234@group.calendar.google.com``.
    ~/.gcalcli_oauth
        Must exist with valid OAuth credentials (see ``docs/google-calendar.md``).

Run:
    LIFE_OS_GCAL_INTEGRATION=1 \\
    LIFE_OS_GCAL_TEST_CALENDAR_ID=<id> \\
    pytest tests/test_gcal_integration.py -v

The tests schedule events 30-90 days in the future and unconditionally delete
every event they create (including a defensive ``clear_life_os_events`` sweep
in ``finally`` blocks), so a failure mid-test does not leak state.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import os
import sys
import uuid
from collections.abc import Iterator
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any

import pytest

INTEGRATION_ENV = "LIFE_OS_GCAL_INTEGRATION"
TEST_CAL_ENV = "LIFE_OS_GCAL_TEST_CALENDAR_ID"
TEST_MARKER_PREFIX = "life-os-integration-test"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get(INTEGRATION_ENV) != "1",
        reason=f"Set {INTEGRATION_ENV}=1 to enable Google Calendar integration tests",
    ),
    pytest.mark.skipif(
        not os.environ.get(TEST_CAL_ENV),
        reason=(
            f"Set {TEST_CAL_ENV} to a dedicated test calendar ID "
            "(do NOT use your primary calendar)"
        ),
    ),
    pytest.mark.skipif(
        not (Path.home() / ".gcalcli_oauth").exists(),
        reason="Google OAuth token not found at ~/.gcalcli_oauth",
    ),
]


def _restore_real_google_modules() -> None:
    """Remove mocked google/googleapiclient modules left by ``test_gcal.py``.

    ``test_gcal.py`` injects ``MagicMock`` objects into ``sys.modules`` at
    import time. Integration tests need the real google-auth /
    google-api-python-client packages, so we evict any mocks before our fresh
    import of ``gcal.py``. Real modules (not ``MagicMock`` instances) are left
    untouched.
    """
    prefixes = ("google", "googleapiclient", "google_auth")
    for name in list(sys.modules):
        if not any(name == p or name.startswith(p + ".") for p in prefixes):
            continue
        mod = sys.modules[name]
        if "Mock" in type(mod).__name__:
            del sys.modules[name]


@pytest.fixture(scope="module")
def gcal_module() -> Any:
    """Load ``gcal.py`` with real Google API modules bound."""
    _restore_real_google_modules()
    try:
        import google.auth  # noqa: F401
        from googleapiclient.discovery import build  # noqa: F401
    except ImportError as exc:
        pytest.skip(f"Real Google API libraries not importable: {exc}")

    module_path = (
        Path(__file__).resolve().parents[1]
        / "01-ops"
        / "life-os"
        / "scripts"
        / "gcal.py"
    )
    spec = spec_from_file_location("life_os_gcal_integration", module_path)
    assert spec is not None
    assert spec.loader is not None
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)

    mod._service_cache = None
    mod._timezone_cache = None
    return mod


@pytest.fixture
def test_calendar_id() -> str:
    return os.environ[TEST_CAL_ENV]


@pytest.fixture
def unique_marker() -> str:
    """Short unique token shared by every event a single test creates."""
    return f"{TEST_MARKER_PREFIX}:{uuid.uuid4().hex[:12]}"


@pytest.fixture
def created_event_ids(gcal_module: Any, test_calendar_id: str) -> Iterator[list[str]]:
    """Collect event IDs created during a test; delete them in teardown."""
    ids: list[str] = []
    yield ids
    for event_id in ids:
        with contextlib.suppress(Exception):
            gcal_module.delete_event(event_id, calendar_id=test_calendar_id)


def _future_datetime(days: int, hour: int = 9) -> dt.datetime:
    return dt.datetime.combine(
        dt.date.today() + dt.timedelta(days=days),
        dt.time(hour, 0, 0),
    )


class TestGcalAuthAndDiscovery:
    def test_list_calendars_returns_list_including_test_calendar(
        self, gcal_module: Any, test_calendar_id: str
    ) -> None:
        calendars = gcal_module.list_calendars()
        assert isinstance(calendars, list)
        assert calendars, "expected at least one calendar for authenticated user"

        ids = {c.get("id") for c in calendars}
        assert test_calendar_id in ids, (
            f"Configured test calendar {test_calendar_id!r} was not returned "
            f"by list_calendars(); got {sorted(ids)}"
        )

    def test_get_service_returns_cached_instance(self, gcal_module: Any) -> None:
        gcal_module._service_cache = None
        service_a = gcal_module.get_service()
        service_b = gcal_module.get_service()
        assert service_a is service_b


class TestGcalEventLifecycle:
    def test_create_then_get_agenda_then_delete(
        self,
        gcal_module: Any,
        test_calendar_id: str,
        unique_marker: str,
        created_event_ids: list[str],
    ) -> None:
        start = _future_datetime(days=30, hour=9)
        end = start + dt.timedelta(hours=1)

        event_id = gcal_module.create_event(
            summary=f"[{unique_marker}] create/delete roundtrip",
            start_dt=start,
            end_dt=end,
            description=f"{gcal_module.LIFE_OS_TAG} {unique_marker}",
            calendar_id=test_calendar_id,
        )
        assert event_id, "create_event returned empty ID"
        created_event_ids.append(event_id)

        agenda = gcal_module.get_agenda(
            start.date(),
            end.date() + dt.timedelta(days=1),
            calendar_id=test_calendar_id,
        )
        assert any(ev["id"] == event_id for ev in agenda), (
            "Created event not visible in get_agenda()"
        )

    def test_update_event_changes_summary_on_server(
        self,
        gcal_module: Any,
        test_calendar_id: str,
        unique_marker: str,
        created_event_ids: list[str],
    ) -> None:
        start = _future_datetime(days=31, hour=10)
        end = start + dt.timedelta(hours=1)
        original = f"[{unique_marker}] original"
        updated = f"[{unique_marker}] updated"

        event_id = gcal_module.create_event(
            summary=original,
            start_dt=start,
            end_dt=end,
            calendar_id=test_calendar_id,
        )
        assert event_id
        created_event_ids.append(event_id)

        result = gcal_module.update_event(
            event_id,
            calendar_id=test_calendar_id,
            summary=updated,
        )
        assert result.get("summary") == updated

        # Verify the new summary persists via an independent search.
        found = gcal_module.search_events(
            unique_marker,
            start.date(),
            end.date() + dt.timedelta(days=1),
            calendar_id=test_calendar_id,
        )
        summaries = [e.get("summary") for e in found if e.get("id") == event_id]
        assert summaries == [updated]

    def test_delete_event_is_noop_on_missing_event(
        self, gcal_module: Any, test_calendar_id: str
    ) -> None:
        # Real Google Calendar responds 404/410 for unknown IDs; gcal.py
        # logs a warning and swallows the error. This must not raise.
        missing = f"nonexistent-{uuid.uuid4().hex}"
        gcal_module.delete_event(missing, calendar_id=test_calendar_id)

    def test_search_events_finds_by_unique_marker(
        self,
        gcal_module: Any,
        test_calendar_id: str,
        unique_marker: str,
        created_event_ids: list[str],
    ) -> None:
        start = _future_datetime(days=32, hour=11)
        end = start + dt.timedelta(hours=1)

        event_id = gcal_module.create_event(
            summary=f"[{unique_marker}] searchable",
            start_dt=start,
            end_dt=end,
            calendar_id=test_calendar_id,
        )
        assert event_id
        created_event_ids.append(event_id)

        matches = gcal_module.search_events(
            unique_marker,
            start.date(),
            end.date() + dt.timedelta(days=1),
            calendar_id=test_calendar_id,
        )
        assert [m["id"] for m in matches if m["id"] == event_id] == [event_id]

        # Negative control: a random token should not match our event.
        nonmatch = gcal_module.search_events(
            uuid.uuid4().hex,
            start.date(),
            end.date() + dt.timedelta(days=1),
            calendar_id=test_calendar_id,
        )
        assert all(m["id"] != event_id for m in nonmatch)


class TestGcalDayPlan:
    def test_push_day_plan_creates_and_clear_life_os_events_removes(
        self,
        gcal_module: Any,
        test_calendar_id: str,
        unique_marker: str,
    ) -> None:
        target_date = dt.date.today() + dt.timedelta(days=60)
        blocks = [
            {
                "start": "09:00",
                "end": "10:00",
                "title": f"{unique_marker} focus",
                "domain": "work",
                "task_id": "T-INT-1",
            },
            {
                "start": "11:00",
                "end": "12:00",
                "title": f"{unique_marker} review",
            },
        ]

        try:
            created = gcal_module.push_day_plan(
                blocks, target_date, calendar_id=test_calendar_id
            )
            assert len(created) == 2, f"expected 2 created events, got {created}"

            agenda = gcal_module.get_agenda(
                target_date,
                target_date + dt.timedelta(days=1),
                calendar_id=test_calendar_id,
            )
            agenda_ids = {ev["id"] for ev in agenda}
            for event_id in created:
                assert event_id in agenda_ids

            cleared = gcal_module.clear_life_os_events(
                target_date, calendar_id=test_calendar_id
            )
            assert cleared >= 2

            agenda_after = gcal_module.get_agenda(
                target_date,
                target_date + dt.timedelta(days=1),
                calendar_id=test_calendar_id,
            )
            remaining_ids = {ev["id"] for ev in agenda_after}
            assert not (set(created) & remaining_ids), (
                "push_day_plan events survived clear_life_os_events()"
            )
        finally:
            # Defensive sweep — guarantees no [life-os] events leak if the
            # body raises before the explicit clear above.
            gcal_module.clear_life_os_events(target_date, calendar_id=test_calendar_id)

    def test_clear_life_os_events_preserves_untagged_events(
        self,
        gcal_module: Any,
        test_calendar_id: str,
        unique_marker: str,
        created_event_ids: list[str],
    ) -> None:
        """Safety invariant: ``clear_life_os_events`` must delete only events
        whose description contains ``LIFE_OS_TAG``. A regression to "delete
        everything in the date range" would wipe the user's personal events
        on the target date, so this is covered against the real API — not
        just mocks in ``tests/test_gcal.py``.
        """
        target_date = dt.date.today() + dt.timedelta(days=62)
        tagged_start = dt.datetime.combine(target_date, dt.time(9, 0))
        tagged_end = tagged_start + dt.timedelta(hours=1)
        untagged_start = dt.datetime.combine(target_date, dt.time(14, 0))
        untagged_end = untagged_start + dt.timedelta(hours=1)

        tagged_id = gcal_module.create_event(
            summary=f"[{unique_marker}] tagged",
            start_dt=tagged_start,
            end_dt=tagged_end,
            description=f"{gcal_module.LIFE_OS_TAG} {unique_marker}",
            calendar_id=test_calendar_id,
        )
        assert tagged_id, "create_event returned empty ID for tagged event"
        created_event_ids.append(tagged_id)

        untagged_id = gcal_module.create_event(
            summary=f"[{unique_marker}] untagged-must-survive",
            start_dt=untagged_start,
            end_dt=untagged_end,
            description=f"personal event {unique_marker} (no life-os tag)",
            calendar_id=test_calendar_id,
        )
        assert untagged_id, "create_event returned empty ID for untagged event"
        created_event_ids.append(untagged_id)

        cleared = gcal_module.clear_life_os_events(
            target_date, calendar_id=test_calendar_id
        )
        assert cleared >= 1, "expected at least the tagged event to be cleared"

        agenda = gcal_module.get_agenda(
            target_date,
            target_date + dt.timedelta(days=1),
            calendar_id=test_calendar_id,
        )
        remaining_ids = {ev["id"] for ev in agenda}
        assert tagged_id not in remaining_ids, (
            "tagged event should have been cleared by clear_life_os_events"
        )
        assert untagged_id in remaining_ids, (
            "clear_life_os_events deleted an event without the "
            f"{gcal_module.LIFE_OS_TAG} tag — that would nuke user calendars"
        )

    def test_push_day_plan_replaces_prior_life_os_events(
        self,
        gcal_module: Any,
        test_calendar_id: str,
        unique_marker: str,
    ) -> None:
        """A second push_day_plan call clears the first plan's events first."""
        target_date = dt.date.today() + dt.timedelta(days=61)
        first = [
            {
                "start": "08:00",
                "end": "09:00",
                "title": f"{unique_marker} first",
            },
        ]
        second = [
            {
                "start": "13:00",
                "end": "14:00",
                "title": f"{unique_marker} second",
            },
        ]

        try:
            ids_first = gcal_module.push_day_plan(
                first, target_date, calendar_id=test_calendar_id
            )
            assert len(ids_first) == 1

            ids_second = gcal_module.push_day_plan(
                second, target_date, calendar_id=test_calendar_id
            )
            assert len(ids_second) == 1

            agenda = gcal_module.get_agenda(
                target_date,
                target_date + dt.timedelta(days=1),
                calendar_id=test_calendar_id,
            )
            agenda_ids = {ev["id"] for ev in agenda}
            assert ids_first[0] not in agenda_ids, (
                "prior plan's event survived second push_day_plan"
            )
            assert ids_second[0] in agenda_ids
        finally:
            gcal_module.clear_life_os_events(target_date, calendar_id=test_calendar_id)
