#!/usr/bin/env python3
"""Google Calendar API wrapper using gcalcli's saved OAuth token."""

from __future__ import annotations

import datetime as dt
import json
import logging
import pickle
import random
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Configure logging
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(log_format)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Module-level caches for performance
_service_cache = None
_timezone_cache = None

# Security constants
MAX_OAUTH_TOKEN_SIZE = 50 * 1024  # 50KB

OAUTH_TOKEN_PATH = Path.home() / ".gcalcli_oauth"
PROFILE_PATH = Path(__file__).resolve().parents[1] / "config" / "profile.json"
LIFE_OS_TAG = "[life-os]"

# Retry policy for transient Google Calendar API errors.
# 429 = rate limit; 500/502/503/504 = server/gateway errors.
RETRYABLE_HTTP_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
MAX_RETRIES = 3
RETRY_INITIAL_DELAY_SEC = 1.0
RETRY_MAX_DELAY_SEC = 32.0

_T = TypeVar("_T")


def _load_timezone() -> str:
    """Load timezone from profile.json, default to America/Los_Angeles."""
    global _timezone_cache
    if _timezone_cache is None:
        try:
            with PROFILE_PATH.open("r", encoding="utf-8") as f:
                _timezone_cache = json.load(f).get("timezone", "America/Los_Angeles")
        except (FileNotFoundError, json.JSONDecodeError):
            _timezone_cache = "America/Los_Angeles"
    return _timezone_cache


def _get_zoneinfo(tz: str) -> ZoneInfo:
    """Return the configured timezone, falling back to Los Angeles."""
    try:
        return ZoneInfo(tz)
    except ZoneInfoNotFoundError:
        return ZoneInfo("America/Los_Angeles")


def _rfc3339(d: dt.date, time_str: str = "00:00:00") -> str:
    """Format a date + time as RFC3339 with timezone offset."""
    tz = _load_timezone()
    zone = _get_zoneinfo(tz)
    try:
        time_value = dt.time.fromisoformat(time_str)
    except ValueError as e:
        logger.warning("Invalid time format '%s', using 00:00:00: %s", time_str, e)
        time_value = dt.time(0, 0, 0)
    moment = dt.datetime.combine(d, time_value, tzinfo=zone)
    return moment.isoformat()


def get_credentials() -> Any:
    """Load OAuth credentials from gcalcli's saved pickle token."""
    from google.auth.transport.requests import Request

    if not OAUTH_TOKEN_PATH.exists():
        error_msg = (
            f"OAuth token not found at {OAUTH_TOKEN_PATH}. "
            "Install and authenticate gcalcli first: gcalcli list"
        )
        raise FileNotFoundError(error_msg)

    # Ensure the token file is within the expected location for security
    try:
        resolved_path = OAUTH_TOKEN_PATH.resolve()
        if not str(resolved_path).startswith(str(Path.home())):
            raise PermissionError("OAuth token file is outside user home directory")

        # Additional security: check file permissions (should be user-only readable)
        file_stat = resolved_path.stat()
        if file_stat.st_mode & 0o077:  # Check if group or other have any permissions
            perms = oct(file_stat.st_mode)
            logger.warning(
                "OAuth token file has overly permissive permissions: %s",
                perms,
            )

    except (OSError, RuntimeError) as e:
        error_msg = f"Cannot validate OAuth token path: {e}"
        raise PermissionError(error_msg) from e

    # Note: pickle.load() can execute arbitrary code. This is acceptable because
    # the token file is in the user's home directory and managed by gcalcli.
    # For additional security, we check file size to prevent huge files
    try:
        file_size = OAUTH_TOKEN_PATH.stat().st_size
        if file_size > MAX_OAUTH_TOKEN_SIZE:
            error_msg = f"OAuth token file unexpectedly large: {file_size} bytes"
            raise ValueError(error_msg)

        with OAUTH_TOKEN_PATH.open("rb") as f:
            # This follows Google's official OAuth credential storage pattern
            creds = pickle.load(f)  # noqa: S301  # nosec B301 - Google OAuth pattern
    except (OSError, pickle.PickleError, ValueError) as e:
        error_msg = f"Cannot load OAuth credentials: {e}"
        raise PermissionError(error_msg) from e

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with OAUTH_TOKEN_PATH.open("wb") as f:
            pickle.dump(creds, f)

    return creds


def get_service() -> Any:
    """Build and return a Google Calendar API service with caching."""
    global _service_cache
    if _service_cache is None:
        from googleapiclient.discovery import build

        creds = get_credentials()
        _service_cache = build(
            "calendar",
            "v3",
            credentials=creds,
            cache_discovery=False,
        )
    return _service_cache


def _log_google_api_error(action: str, exc: Exception) -> None:
    """Log Google API errors consistently without requiring the dependency at import time."""
    try:
        from googleapiclient.errors import HttpError

        if isinstance(exc, HttpError):
            logger.error(
                "Google Calendar API error while %s (HTTP %s): %s",
                action,
                exc.resp.status,
                exc,
            )
            return
    except ImportError:
        pass

    logger.error("Unexpected error while %s: %s", action, exc)


def _is_http_error_status(exc: Exception, status: int) -> bool:
    """Return whether the given exception is a matching Google API HttpError."""
    try:
        from googleapiclient.errors import HttpError

        return isinstance(exc, HttpError) and exc.resp.status == status
    except ImportError:
        return False


def _is_retryable_http_error(exc: Exception) -> bool:
    """Return whether the exception is a transient Google API HttpError worth retrying."""
    try:
        from googleapiclient.errors import HttpError

        if not isinstance(exc, HttpError):
            return False
        return exc.resp.status in RETRYABLE_HTTP_STATUS_CODES
    except ImportError:
        return False


def _compute_retry_delay(attempt: int) -> float:
    """Return exponential backoff delay in seconds with bounded jitter.

    attempt is 0-indexed: attempt 0 waits ~RETRY_INITIAL_DELAY_SEC, attempt 1
    waits ~2x that, capped at RETRY_MAX_DELAY_SEC. Jitter adds up to 25% on
    top to avoid thundering-herd retries. Not used for crypto, so the
    standard PRNG is fine here.
    """
    base = min(RETRY_INITIAL_DELAY_SEC * (2**attempt), RETRY_MAX_DELAY_SEC)
    jitter_fraction = random.uniform(0, 0.25)  # noqa: S311
    return float(base + base * jitter_fraction)


def _execute_with_retry(  # noqa: UP047 - Python 3.11 compatibility
    request_callable: Callable[[], _T],
    action_desc: str,
    max_retries: int = MAX_RETRIES,
) -> _T:
    """Execute a Google API request, retrying on transient HTTP errors.

    Retries up to max_retries times with exponential backoff on 429/5xx errors.
    Non-retryable errors (404, 403, auth failures, etc.) are re-raised immediately
    so callers can apply their own handling.
    """
    attempt = 0
    while True:
        try:
            return request_callable()
        except Exception as exc:
            if attempt >= max_retries or not _is_retryable_http_error(exc):
                raise
            delay = _compute_retry_delay(attempt)
            logger.warning(
                "Transient error while %s (attempt %d/%d), retrying in %.2fs: %s",
                action_desc,
                attempt + 1,
                max_retries,
                delay,
                exc,
            )
            time.sleep(delay)
            attempt += 1


def _parse_block_time(date: dt.date, time_str: str, field_name: str) -> dt.datetime:
    """Parse HH:MM or HH:MM:SS block times for a specific date."""
    try:
        time_value = dt.time.fromisoformat(time_str)
    except ValueError as exc:
        error_msg = f"invalid {field_name} time '{time_str}'"
        raise ValueError(error_msg) from exc

    return dt.datetime.combine(
        date,
        dt.time(time_value.hour, time_value.minute),
    )


def list_calendars() -> list[dict[str, Any]]:
    """List all calendars accessible by the authenticated user."""
    try:
        service = get_service()
        result = _execute_with_retry(
            lambda: service.calendarList().list().execute(),
            "fetching calendar list",
        )
        return result.get("items", [])  # type: ignore[no-any-return]
    except (FileNotFoundError, PermissionError):
        logger.exception("Authentication error while fetching calendar list")
        return []
    except Exception as e:
        _log_google_api_error("fetching calendar list", e)
        return []


def get_agenda(
    start_date: dt.date,
    end_date: dt.date | None = None,
    calendar_id: str = "primary",
) -> list[dict[str, Any]]:
    """Get events between start_date and end_date (inclusive)."""
    try:
        if end_date is None:
            end_date = start_date + dt.timedelta(days=1)

        tz = _load_timezone()
        time_min = _rfc3339(start_date)
        time_max = _rfc3339(end_date)

        service = get_service()
        events = []
        page_token: str | None = None

        while True:

            def _fetch_page(token: str | None = page_token) -> dict[str, Any]:
                response: dict[str, Any] = (
                    service.events()
                    .list(
                        calendarId=calendar_id,
                        timeMin=time_min,
                        timeMax=time_max,
                        timeZone=tz,
                        singleEvents=True,
                        orderBy="startTime",
                        pageToken=token,
                    )
                    .execute()
                )
                return response

            result = _execute_with_retry(
                _fetch_page,
                f"fetching events for {start_date}",
            )

            events.extend(result.get("items", []))
            page_token = result.get("nextPageToken")
            if not page_token:
                break
        return events
    except (FileNotFoundError, PermissionError):
        logger.exception(
            "Authentication error while fetching events for %s",
            start_date,
        )
        return []
    except Exception as e:
        _log_google_api_error(f"fetching events for {start_date}", e)
        return []


def create_event(
    summary: str,
    start_dt: dt.datetime,
    end_dt: dt.datetime,
    location: str | None = None,
    description: str | None = None,
    reminders: dict | None = None,
    calendar_id: str = "primary",
) -> str:
    """Create a calendar event. Returns the event ID or empty string on failure."""
    try:
        tz = _load_timezone()

        body: dict[str, Any] = {
            "summary": summary,
            "start": {"dateTime": start_dt.isoformat(), "timeZone": tz},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": tz},
        }
        if location:
            body["location"] = location
        if description:
            body["description"] = description
        if reminders:
            body["reminders"] = reminders

        service = get_service()
        event = _execute_with_retry(
            lambda: (
                service.events().insert(calendarId=calendar_id, body=body).execute()
            ),
            f"creating event '{summary}'",
        )
        return event["id"]  # type: ignore[no-any-return]
    except (FileNotFoundError, PermissionError):
        logger.exception("Authentication error while creating event '%s'", summary)
        return ""
    except ValueError:
        logger.exception("Invalid input while creating event '%s'", summary)
        return ""
    except Exception as e:
        _log_google_api_error(f"creating event '{summary}'", e)
        return ""


def update_event(
    event_id: str,
    calendar_id: str = "primary",
    **kwargs: Any,
) -> dict[str, Any]:
    """Update an existing event. Pass fields to update as kwargs."""
    try:
        service = get_service()
        event = _execute_with_retry(
            lambda: (
                service.events().get(calendarId=calendar_id, eventId=event_id).execute()
            ),
            f"fetching event {event_id}",
        )

        tz = _load_timezone()
        for key, value in kwargs.items():
            if key in ("start", "end") and isinstance(value, dt.datetime):
                event[key] = {"dateTime": value.isoformat(), "timeZone": tz}
            else:
                event[key] = value

        updated = _execute_with_retry(
            lambda: (
                service.events()
                .update(calendarId=calendar_id, eventId=event_id, body=event)
                .execute()
            ),
            f"updating event {event_id}",
        )
        return updated  # type: ignore[no-any-return]
    except (FileNotFoundError, PermissionError):
        logger.exception("Authentication error while updating event %s", event_id)
        return {}
    except ValueError:
        logger.exception("Invalid input while updating event %s", event_id)
        return {}
    except Exception as e:
        _log_google_api_error(f"updating event {event_id}", e)
        return {}


def delete_event(event_id: str, calendar_id: str = "primary") -> None:
    """Delete an event by ID."""
    try:
        service = get_service()
        _execute_with_retry(
            lambda: (
                service.events()
                .delete(calendarId=calendar_id, eventId=event_id)
                .execute()
            ),
            f"deleting event {event_id}",
        )
    except (FileNotFoundError, PermissionError):
        logger.exception("Authentication error while deleting event %s", event_id)
    except Exception as e:
        if _is_http_error_status(e, 404):
            logger.warning(
                "Event %s not found (already deleted or never existed)",
                event_id,
            )
        else:
            _log_google_api_error(f"deleting event {event_id}", e)


def search_events(
    query: str,
    start_date: dt.date,
    end_date: dt.date,
    calendar_id: str = "primary",
) -> list[dict[str, Any]]:
    """Search events by text query within a date range."""
    try:
        tz = _load_timezone()
        time_min = _rfc3339(start_date)
        time_max = _rfc3339(end_date)

        service = get_service()
        result = _execute_with_retry(
            lambda: (
                service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    timeZone=tz,
                    q=query,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            ),
            f"searching events for '{query}'",
        )
        return result.get("items", [])  # type: ignore[no-any-return]
    except (FileNotFoundError, PermissionError):
        logger.exception("Authentication error while searching events for '%s'", query)
        return []
    except Exception as e:
        _log_google_api_error(f"searching events for '{query}'", e)
        return []


def clear_life_os_events(date: dt.date, calendar_id: str = "primary") -> int:
    """Delete all events tagged with [life-os] on a given date. Returns count deleted."""
    next_day = date + dt.timedelta(days=1)
    events = get_agenda(date, next_day, calendar_id=calendar_id)

    # Collect events to delete first, then delete in batch for better performance
    events_to_delete = []
    for ev in events:
        desc = ev.get("description", "") or ""
        if LIFE_OS_TAG in desc:
            events_to_delete.append(ev["id"])

    # Delete events
    deleted = 0
    for event_id in events_to_delete:
        delete_event(event_id, calendar_id=calendar_id)
        deleted += 1

    return deleted


def push_day_plan(
    blocks: list[dict[str, str]],
    date: dt.date,
    calendar_id: str = "primary",
) -> list[str]:
    """Batch-create calendar events from time blocks with automatic cleanup.

    This function first clears all existing [life-os] tagged events for the given date,
    then creates new events from the provided time blocks. Events that span midnight
    are automatically adjusted to the next day. Invalid time formats are logged and skipped.

    Args:
        blocks: List of dictionaries, each containing:
            - start: Time string in HH:MM format
            - end: Time string in HH:MM format
            - title: Event title
            - domain: Optional domain/category
            - task_id: Optional task identifier
        date: Target date for the events
        calendar_id: Google Calendar ID (defaults to "primary")

    Returns:
        List of successfully created event IDs

    Raises:
        No exceptions are raised; errors are logged and operation continues.

    """
    cleared = clear_life_os_events(date, calendar_id=calendar_id)
    if cleared:
        logger.info("Cleared %s existing %s events for %s", cleared, LIFE_OS_TAG, date)

    created_ids = []
    skipped_blocks = 0

    for block in blocks:
        start_str = block.get("start", "")
        end_str = block.get("end", "")
        title = block.get("title", "Untitled")
        domain = block.get("domain", "")
        task_id = block.get("task_id", "")

        try:
            start_dt = _parse_block_time(date, start_str, "start")
            end_dt = _parse_block_time(date, end_str, "end")

            # Handle end time on next day if earlier than start time
            if end_dt <= start_dt:
                end_dt += dt.timedelta(days=1)
                logger.info(
                    "Block '%s' spans midnight, end time adjusted to next day",
                    title,
                )

        except ValueError as e:
            logger.warning("Skipping block '%s': invalid time format - %s", title, e)
            skipped_blocks += 1
            continue

        summary = f"[{domain}] {title}" if domain else title
        desc_parts = [LIFE_OS_TAG, "Source: auto_planner"]
        if task_id:
            desc_parts.append(f"Task: {task_id}")
        description = "\n".join(desc_parts)

        event_id = create_event(
            summary=summary,
            start_dt=start_dt,
            end_dt=end_dt,
            description=description,
            calendar_id=calendar_id,
        )
        if event_id:  # Only add successful creations
            created_ids.append(event_id)

    # Log summary of the operation
    total_blocks = len(blocks)
    successful_blocks = len(created_ids)
    failed_blocks = total_blocks - successful_blocks - skipped_blocks

    if skipped_blocks > 0:
        logger.warning(
            "Day plan push summary: %s/%s created, %s skipped due to invalid time format",
            successful_blocks,
            total_blocks,
            skipped_blocks,
        )
    if failed_blocks > 0:
        logger.error(
            "Day plan push summary: %s blocks failed to create events",
            failed_blocks,
        )
    if successful_blocks > 0:
        logger.info(
            "Successfully created %s calendar events for %s",
            successful_blocks,
            date,
        )

    return created_ids


def format_event_line(event: dict[str, Any]) -> str:
    """Format a single event for display."""
    start = event.get("start", {})
    end = event.get("end", {})

    start_str = start.get("dateTime", start.get("date", ""))
    end_str = end.get("dateTime", end.get("date", ""))

    # Extract just the time portion for dateTime values
    if "T" in start_str:
        start_str = start_str.split("T")[1][:5]
    if "T" in end_str:
        end_str = end_str.split("T")[1][:5]

    summary = event.get("summary", "(no title)")
    location = event.get("location", "")

    line = f"  {start_str} - {end_str}  {summary}"
    if location:
        line += f"  ({location})"
    return line
