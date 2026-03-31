#!/usr/bin/env python3
"""Google Calendar API wrapper using gcalcli's saved OAuth token."""
from __future__ import annotations

import datetime as dt
import json
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

OAUTH_TOKEN_PATH = Path.home() / ".gcalcli_oauth"
PROFILE_PATH = Path(__file__).resolve().parents[1] / "config" / "profile.json"
LIFE_OS_TAG = "[life-os]"


def _load_timezone() -> str:
    """Load timezone from profile.json, default to America/Los_Angeles."""
    try:
        with PROFILE_PATH.open("r", encoding="utf-8") as f:
            return json.load(f).get("timezone", "America/Los_Angeles")
    except (FileNotFoundError, json.JSONDecodeError):
        return "America/Los_Angeles"


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
    time_value = dt.time.fromisoformat(time_str)
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
    with OAUTH_TOKEN_PATH.open("rb") as f:
        creds = pickle.load(f)

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with OAUTH_TOKEN_PATH.open("wb") as f:
            pickle.dump(creds, f)

    return creds


def get_service():
    """Build and return a Google Calendar API service."""
    from googleapiclient.discovery import build

    creds = get_credentials()
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def list_calendars() -> List[Dict[str, Any]]:
    """List all calendars accessible by the authenticated user."""
    service = get_service()
    result = service.calendarList().list().execute()
    return result.get("items", [])


def get_agenda(
    start_date: dt.date,
    end_date: Optional[dt.date] = None,
    calendar_id: str = "primary",
) -> List[Dict[str, Any]]:
    """Get events between start_date and end_date (inclusive)."""
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


def create_event(
    summary: str,
    start_dt: dt.datetime,
    end_dt: dt.datetime,
    location: Optional[str] = None,
    description: Optional[str] = None,
    reminders: Optional[Dict] = None,
    calendar_id: str = "primary",
) -> str:
    """Create a calendar event. Returns the event ID."""
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


def update_event(
    event_id: str,
    calendar_id: str = "primary",
    **kwargs: Any,
) -> Dict[str, Any]:
    """Update an existing event. Pass fields to update as kwargs."""
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


def delete_event(event_id: str, calendar_id: str = "primary") -> None:
    """Delete an event by ID."""
    service = get_service()
    service.events().delete(calendarId=calendar_id, eventId=event_id).execute()


def search_events(
    query: str,
    start_date: dt.date,
    end_date: dt.date,
    calendar_id: str = "primary",
) -> List[Dict[str, Any]]:
    """Search events by text query within a date range."""
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
        print(f"Cleared {cleared} existing {LIFE_OS_TAG} events for {date}")

    created_ids = []
    for block in blocks:
        start_str = block.get("start", "")
        end_str = block.get("end", "")
        title = block.get("title", "Untitled")
        domain = block.get("domain", "")
        task_id = block.get("task_id", "")

        start_parts = start_str.split(":")
        end_parts = end_str.split(":")
        if len(start_parts) < 2 or len(end_parts) < 2:
            continue

        start_dt = dt.datetime(
            date.year, date.month, date.day,
            int(start_parts[0]), int(start_parts[1]),
        )
        end_dt = dt.datetime(
            date.year, date.month, date.day,
            int(end_parts[0]), int(end_parts[1]),
        )

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
        created_ids.append(event_id)

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
