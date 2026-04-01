#!/usr/bin/env python3
"""Google Calendar API wrapper using gcalcli's saved OAuth token."""
from __future__ import annotations

import datetime as dt
import json
import logging
import pickle
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Configure logging
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Module-level caches for performance
_service_cache = None
_timezone_cache = None

OAUTH_TOKEN_PATH = Path.home() / ".gcalcli_oauth"
PROFILE_PATH = Path(__file__).resolve().parents[1] / "config" / "profile.json"
LIFE_OS_TAG = "[life-os]"
DEFAULT_TIMEZONE = "America/Los_Angeles"
DEFAULT_TIME = "00:00:00"
CALENDAR_API_VERSION = "v3"
TIME_FORMAT_PATTERN = re.compile(r"^([01]?[0-9]|2[0-3]):([0-5][0-9])$")


def _load_timezone() -> str:
    """Load timezone from profile.json, default to America/Los_Angeles."""
    global _timezone_cache
    if _timezone_cache is None:
        try:
            with PROFILE_PATH.open("r", encoding="utf-8") as f:
                _timezone_cache = json.load(f).get("timezone", DEFAULT_TIMEZONE)
        except (FileNotFoundError, json.JSONDecodeError):
            _timezone_cache = DEFAULT_TIMEZONE
    return _timezone_cache


def _get_zoneinfo(tz: str) -> ZoneInfo:
    """Return the configured timezone, falling back to Los Angeles."""
    try:
        return ZoneInfo(tz)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_TIMEZONE)


def _rfc3339(d: dt.date, time_str: str = DEFAULT_TIME) -> str:
    """Format a date + time as RFC3339 with timezone offset."""
    tz = _load_timezone()
    zone = _get_zoneinfo(tz)
    try:
        time_value = dt.time.fromisoformat(time_str)
    except ValueError as e:
        logger.warning(f"Invalid time format '{time_str}', using {DEFAULT_TIME}: {e}")
        time_value = dt.time(0, 0, 0)
    moment = dt.datetime.combine(d, time_value, tzinfo=zone)
    return moment.isoformat()


def get_credentials():
    """Load OAuth credentials from gcalcli's saved pickle token."""
    from google.auth.transport.requests import Request

    if not OAUTH_TOKEN_PATH.exists():
        raise FileNotFoundError(
            f"OAuth token not found at {OAUTH_TOKEN_PATH}. "
            "Install and authenticate gcalcli first: gcalcli list"
        )

    # Ensure the token file is within the expected location for security
    try:
        resolved_path = OAUTH_TOKEN_PATH.resolve()
        if not str(resolved_path).startswith(str(Path.home())):
            raise PermissionError("OAuth token file is outside user home directory")
    except (OSError, RuntimeError) as e:
        raise PermissionError(f"Cannot validate OAuth token path: {e}") from e

    # Note: pickle.load() can execute arbitrary code. This is acceptable because
    # the token file is in the user's home directory and managed by gcalcli.
    with OAUTH_TOKEN_PATH.open("rb") as f:
        creds = pickle.load(f)

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with OAUTH_TOKEN_PATH.open("wb") as f:
            pickle.dump(creds, f)

    return creds


def get_service():
    """Build and return a Google Calendar API service with caching."""
    global _service_cache
    if _service_cache is None:
        from googleapiclient.discovery import build
        creds = get_credentials()
        _service_cache = build("calendar", CALENDAR_API_VERSION, credentials=creds, cache_discovery=False)
    return _service_cache


def _handle_api_exception(e: Exception, operation_desc: str, return_value: Any = None) -> Any:
    """Centralized exception handling for Google Calendar API operations."""
    if isinstance(e, (FileNotFoundError, PermissionError)):
        logger.error(f"Authentication error while {operation_desc}: {e}")
    else:
        try:
            from googleapiclient.errors import HttpError
            if isinstance(e, HttpError):
                logger.error(f"Google Calendar API error while {operation_desc} (HTTP {e.resp.status}): {e}")
            else:
                logger.error(f"Unexpected error while {operation_desc}: {e}")
        except ImportError:
            logger.error(f"Error while {operation_desc}: {e}")
    return return_value


def list_calendars() -> List[Dict[str, Any]]:
    """List all calendars accessible by the authenticated user."""
    try:
        service = get_service()
        result = service.calendarList().list().execute()
        return result.get("items", [])
    except Exception as e:
        return _handle_api_exception(e, "fetching calendar list", [])


def get_agenda(
    start_date: dt.date,
    end_date: Optional[dt.date] = None,
    calendar_id: str = "primary",
) -> List[Dict[str, Any]]:
    """Get events between start_date and end_date (inclusive)."""
    try:
        if end_date is None:
            end_date = start_date + dt.timedelta(days=1)

        tz = _load_timezone()
        time_min = _rfc3339(start_date)
        time_max = _rfc3339(end_date)

        service = get_service()
        events = []
        page_token = None

        while True:
            result = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                timeZone=tz,
                singleEvents=True,
                orderBy="startTime",
                pageToken=page_token,
            ).execute()

            events.extend(result.get("items", []))
            page_token = result.get("nextPageToken")
            if not page_token:
                break

        return events
    except Exception as e:
        return _handle_api_exception(e, f"fetching events for {start_date}", [])


def create_event(
    summary: str,
    start_dt: dt.datetime,
    end_dt: dt.datetime,
    location: Optional[str] = None,
    description: Optional[str] = None,
    reminders: Optional[Dict] = None,
    calendar_id: str = "primary",
) -> str:
    """Create a calendar event. Returns the event ID or empty string on failure."""
    try:
        tz = _load_timezone()

        body: Dict[str, Any] = {
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
        event = service.events().insert(calendarId=calendar_id, body=body).execute()
        return event["id"]
    except ValueError as e:
        logger.error(f"Invalid input while creating event '{summary}': {e}")
        return ""
    except Exception as e:
        return _handle_api_exception(e, f"creating event '{summary}'", "")


def update_event(
    event_id: str,
    calendar_id: str = "primary",
    **kwargs: Any,
) -> Dict[str, Any]:
    """Update an existing event. Pass fields to update as kwargs."""
    try:
        service = get_service()
        event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()

        tz = _load_timezone()
        for key, value in kwargs.items():
            if key in ("start", "end") and isinstance(value, dt.datetime):
                event[key] = {"dateTime": value.isoformat(), "timeZone": tz}
            else:
                event[key] = value

        updated = service.events().update(
            calendarId=calendar_id, eventId=event_id, body=event
        ).execute()
        return updated
    except ValueError as e:
        logger.error(f"Invalid input while updating event {event_id}: {e}")
        return {}
    except Exception as e:
        return _handle_api_exception(e, f"updating event {event_id}", {})


def delete_event(event_id: str, calendar_id: str = "primary") -> None:
    """Delete an event by ID."""
    try:
        service = get_service()
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
    except Exception as e:
        # Special handling for 404 errors in delete operations
        try:
            from googleapiclient.errors import HttpError
            if isinstance(e, HttpError) and e.resp.status == 404:
                logger.warning(f"Event {event_id} not found (already deleted or never existed)")
                return
        except ImportError:
            pass
        _handle_api_exception(e, f"deleting event {event_id}", None)


def search_events(
    query: str,
    start_date: dt.date,
    end_date: dt.date,
    calendar_id: str = "primary",
) -> List[Dict[str, Any]]:
    """Search events by text query within a date range."""
    try:
        tz = _load_timezone()
        time_min = _rfc3339(start_date)
        time_max = _rfc3339(end_date)

        service = get_service()
        result = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            timeZone=tz,
            q=query,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        return result.get("items", [])
    except Exception as e:
        return _handle_api_exception(e, f"searching events for '{query}'", [])


def clear_life_os_events(date: dt.date, calendar_id: str = "primary") -> int:
    """Delete all events tagged with [life-os] on a given date. Returns count deleted."""
    next_day = date + dt.timedelta(days=1)
    events = get_agenda(date, next_day, calendar_id=calendar_id)

    deleted = 0
    for ev in events:
        desc = ev.get("description", "") or ""
        if LIFE_OS_TAG in desc:
            delete_event(ev["id"], calendar_id=calendar_id)
            deleted += 1

    return deleted


def push_day_plan(
    blocks: List[Dict[str, str]],
    date: dt.date,
    calendar_id: str = "primary",
) -> List[str]:
    """Batch-create calendar events from time blocks.

    Each block should have: start (HH:MM), end (HH:MM), title, domain, task_id.
    Clears existing [life-os] events for the date first.
    Returns list of created event IDs.
    """
    cleared = clear_life_os_events(date, calendar_id=calendar_id)
    if cleared:
        logger.info(f"Cleared {cleared} existing {LIFE_OS_TAG} events for {date}")

    created_ids = []
    skipped_blocks = 0

    for block in blocks:
        start_str = block.get("start", "")
        end_str = block.get("end", "")
        title = block.get("title", "Untitled")
        domain = block.get("domain", "")
        task_id = block.get("task_id", "")

        # Validate time format using regex
        if not TIME_FORMAT_PATTERN.match(start_str) or not TIME_FORMAT_PATTERN.match(end_str):
            logger.warning(f"Skipping block '{title}': invalid time format (start='{start_str}', end='{end_str}') - use HH:MM format")
            skipped_blocks += 1
            continue

        try:
            start_parts = start_str.split(":")
            end_parts = end_str.split(":")
            start_hour, start_min = int(start_parts[0]), int(start_parts[1])
            end_hour, end_min = int(end_parts[0]), int(end_parts[1])

            start_dt = dt.datetime(date.year, date.month, date.day, start_hour, start_min)
            end_dt = dt.datetime(date.year, date.month, date.day, end_hour, end_min)

            # Handle end time on next day if earlier than start time
            if end_dt <= start_dt:
                end_dt += dt.timedelta(days=1)
                logger.info(f"Block '{title}' spans midnight, end time adjusted to next day")

        except (ValueError, IndexError) as e:
            logger.warning(f"Skipping block '{title}': invalid time format - {e}")
            skipped_blocks += 1
            continue

        summary = f"[{domain}] {title}" if domain else title
        desc_parts = [LIFE_OS_TAG, f"Source: auto_planner"]
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
        logger.warning(f"Day plan push summary: {successful_blocks}/{total_blocks} created, {skipped_blocks} skipped due to invalid time format")
    if failed_blocks > 0:
        logger.error(f"Day plan push summary: {failed_blocks} blocks failed to create events")
    if successful_blocks > 0:
        logger.info(f"Successfully created {successful_blocks} calendar events for {date}")

    return created_ids


def format_event_line(event: Dict[str, Any]) -> str:
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
