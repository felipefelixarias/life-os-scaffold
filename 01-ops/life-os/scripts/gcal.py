#!/usr/bin/env python3
"""Google Calendar API wrapper using gcalcli's saved OAuth token."""
from __future__ import annotations

import datetime as dt
import json
import logging
import pickle
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


def _load_timezone() -> str:
    """Load timezone from profile.json with safe fallback.

    Returns:
        Timezone string from profile configuration, or 'America/Los_Angeles'
        as fallback if profile is missing or malformed.

    Caches result for performance on subsequent calls.
    """
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

    # Improved time parsing with better validation
    try:
        # Handle different time formats
        if ":" not in time_str:
            raise ValueError(f"Time string '{time_str}' missing colon separator")

        parts = time_str.split(":")
        if len(parts) == 2:
            # HH:MM format
            hour, minute = int(parts[0]), int(parts[1])
            second = 0
        elif len(parts) == 3:
            # HH:MM:SS format
            hour, minute, second = int(parts[0]), int(parts[1]), int(parts[2])
        else:
            raise ValueError(f"Invalid time format '{time_str}', expected HH:MM or HH:MM:SS")

        # Validate ranges
        if not (0 <= hour <= 23):
            raise ValueError(f"Invalid hour {hour}, must be 0-23")
        if not (0 <= minute <= 59):
            raise ValueError(f"Invalid minute {minute}, must be 0-59")
        if not (0 <= second <= 59):
            raise ValueError(f"Invalid second {second}, must be 0-59")

        time_value = dt.time(hour, minute, second)
    except (ValueError, TypeError) as e:
        logger.warning(f"Invalid time format '{time_str}', using 00:00:00: {e}")
        time_value = dt.time(0, 0, 0)

    moment = dt.datetime.combine(d, time_value, tzinfo=zone)
    return moment.isoformat()


def get_credentials() -> Any:
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

    # Validate token file size and permissions for additional security
    try:
        stat_info = OAUTH_TOKEN_PATH.stat()
        if stat_info.st_size == 0:
            raise ValueError("OAuth token file is empty")
        if stat_info.st_size > 1024 * 1024:  # 1MB limit
            logger.warning(f"OAuth token file is unusually large ({stat_info.st_size} bytes)")
    except OSError as e:
        raise PermissionError(f"Cannot access OAuth token file: {e}") from e

    # Note: pickle.load() can execute arbitrary code. This is acceptable because
    # the token file is in the user's home directory and managed by gcalcli.
    try:
        with OAUTH_TOKEN_PATH.open("rb") as f:
            creds = pickle.load(f)
    except (pickle.UnpicklingError, EOFError, UnicodeDecodeError) as e:
        raise ValueError(f"Corrupted OAuth token file: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Unexpected error loading OAuth token: {e}") from e

    # Validate credentials object
    if not hasattr(creds, 'expired') or not hasattr(creds, 'valid'):
        raise ValueError("Invalid credentials object loaded from token file")

    try:
        if creds.expired and creds.refresh_token:
            logger.info("Refreshing expired OAuth credentials")
            creds.refresh(Request())
            # Atomically write the refreshed token to prevent corruption
            temp_path = OAUTH_TOKEN_PATH.with_suffix('.tmp')
            with temp_path.open("wb") as f:
                pickle.dump(creds, f)
            temp_path.replace(OAUTH_TOKEN_PATH)
            logger.info("OAuth credentials refreshed successfully")
        elif creds.expired and not creds.refresh_token:
            raise ValueError("OAuth credentials expired and no refresh token available")
    except Exception as e:
        logger.error(f"Failed to refresh OAuth credentials: {e}")
        raise RuntimeError(f"Cannot refresh expired credentials: {e}") from e

    if not creds.valid:
        raise ValueError("OAuth credentials are invalid")

    return creds


def get_service() -> Any:
    """Build and return a Google Calendar API service with caching."""
    global _service_cache
    if _service_cache is None:
        from googleapiclient.discovery import build
        creds = get_credentials()
        _service_cache = build("calendar", "v3", credentials=creds, cache_discovery=False)
    return _service_cache


def _log_google_api_error(action: str, exc: Exception) -> None:
    """Log Google API errors consistently without requiring the dependency at import time."""
    try:
        from googleapiclient.errors import HttpError
        if isinstance(exc, HttpError):
            logger.error(f"Google Calendar API error while {action} (HTTP {exc.resp.status}): {exc}")
            return
    except ImportError:
        pass

    logger.error(f"Unexpected error while {action}: {exc}")


def list_calendars() -> List[Dict[str, Any]]:
    """List all calendars accessible by the authenticated user."""
    try:
        service = get_service()
        result = service.calendarList().list().execute()
        return result.get("items", [])
    except (FileNotFoundError, PermissionError) as e:
        logger.error(f"Authentication error while fetching calendar list: {e}")
        return []
    except Exception as e:
        _log_google_api_error("fetching calendar list", e)
        return []


def get_agenda(
    start_date: dt.date,
    end_date: Optional[dt.date] = None,
    calendar_id: str = "primary",
    max_retries: int = 3,
    retry_delay: float = 1.0,
) -> List[Dict[str, Any]]:
    """Get events between start_date and end_date (inclusive).

    Args:
        start_date: Start date for event query
        end_date: End date for event query (defaults to start_date + 1 day)
        calendar_id: Google Calendar ID (defaults to "primary")
        max_retries: Maximum number of retry attempts for rate limiting
        retry_delay: Base delay in seconds between retries
    """
    import time

    try:
        if end_date is None:
            end_date = start_date + dt.timedelta(days=1)

        # Validate date range
        if end_date < start_date:
            raise ValueError(f"End date {end_date} cannot be before start date {start_date}")

        date_range_days = (end_date - start_date).days
        if date_range_days > 365:
            logger.warning(f"Large date range requested: {date_range_days} days")

        tz = _load_timezone()
        time_min = _rfc3339(start_date)
        time_max = _rfc3339(end_date)

        service = get_service()
        events = []
        page_token = None
        retry_count = 0

        while True:
            try:
                result = service.events().list(
                    calendarId=calendar_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    timeZone=tz,
                    singleEvents=True,
                    orderBy="startTime",
                    pageToken=page_token,
                    maxResults=250,  # Reasonable page size
                ).execute()

                events.extend(result.get("items", []))
                page_token = result.get("nextPageToken")
                if not page_token:
                    break

                retry_count = 0  # Reset retry count on successful page

            except Exception as e:
                try:
                    from googleapiclient.errors import HttpError
                    if isinstance(e, HttpError):
                        if e.resp.status == 429 and retry_count < max_retries:  # Rate limited
                            retry_count += 1
                            delay = retry_delay * (2 ** (retry_count - 1))  # Exponential backoff
                            logger.warning(f"Rate limited, retrying in {delay:.1f}s (attempt {retry_count}/{max_retries})")
                            time.sleep(delay)
                            continue
                        elif e.resp.status == 404:
                            logger.error(f"Calendar '{calendar_id}' not found")
                            return []
                        elif e.resp.status == 403:
                            logger.error(f"Access denied to calendar '{calendar_id}'")
                            return []
                except ImportError:
                    pass

                # Re-raise if not a retryable error or max retries exceeded
                raise

        logger.info(f"Retrieved {len(events)} events from {start_date} to {end_date}")
        return events

    except (FileNotFoundError, PermissionError) as e:
        logger.error(f"Authentication error while fetching events for {start_date}: {e}")
        return []
    except ValueError as e:
        logger.error(f"Invalid input while fetching events for {start_date}: {e}")
        return []
    except Exception as e:
        _log_google_api_error(f"fetching events for {start_date}", e)
        return []


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
        # Input validation for security
        if len(summary) > 1000:
            logger.warning(f"Event summary truncated from {len(summary)} to 1000 characters")
            summary = summary[:1000]

        if description and len(description) > 8000:
            logger.warning(f"Event description truncated from {len(description)} to 8000 characters")
            description = description[:8000]

        if location and len(location) > 1000:
            logger.warning(f"Event location truncated from {len(location)} to 1000 characters")
            location = location[:1000]

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
    except (FileNotFoundError, PermissionError) as e:
        logger.error(f"Authentication error while creating event '{summary}': {e}")
        return ""
    except ValueError as e:
        logger.error(f"Invalid input while creating event '{summary}': {e}")
        return ""
    except Exception as e:
        _log_google_api_error(f"creating event '{summary}'", e)
        return ""


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
    except (FileNotFoundError, PermissionError) as e:
        logger.error(f"Authentication error while updating event {event_id}: {e}")
        return {}
    except ValueError as e:
        logger.error(f"Invalid input while updating event {event_id}: {e}")
        return {}
    except Exception as e:
        _log_google_api_error(f"updating event {event_id}", e)
        return {}


def delete_event(event_id: str, calendar_id: str = "primary") -> None:
    """Delete an event by ID."""
    try:
        service = get_service()
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
    except (FileNotFoundError, PermissionError) as e:
        logger.error(f"Authentication error while deleting event {event_id}: {e}")
    except Exception as e:
        try:
            from googleapiclient.errors import HttpError
            if isinstance(e, HttpError):
                if e.resp.status == 404:
                    logger.warning(f"Event {event_id} not found (already deleted or never existed)")
                else:
                    logger.error(f"Google Calendar API error while deleting event {event_id} (HTTP {e.resp.status}): {e}")
            else:
                logger.error(f"Unexpected error while deleting event {event_id}: {e}")
        except ImportError:
            logger.error(f"Error while deleting event {event_id}: {e}")


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
    except (FileNotFoundError, PermissionError) as e:
        logger.error(f"Authentication error while searching events for '{query}': {e}")
        return []
    except Exception as e:
        try:
            from googleapiclient.errors import HttpError
            if isinstance(e, HttpError):
                logger.error(f"Google Calendar API error while searching events for '{query}' (HTTP {e.resp.status}): {e}")
            else:
                logger.error(f"Unexpected error while searching events for '{query}': {e}")
        except ImportError:
            logger.error(f"Error while searching events for '{query}': {e}")
        return []


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


def _validate_time_block(block: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """Validate and normalize a time block dictionary.

    Args:
        block: Dictionary containing time block data with expected keys:
               'start', 'end', 'title', 'domain', 'task_id'

    Returns:
        Normalized block data dictionary with parsed time components,
        or None if validation fails.

    Validates:
        - Required time fields (start, end) are present and well-formatted
        - Time values are within valid 24-hour range (00:00-23:59)
        - Title is not empty (defaults to "Untitled" if missing)
        - No malformed time strings
    """
    if not isinstance(block, dict):
        logger.warning("Block is not a dictionary")
        return None

    start_str = str(block.get("start", "")).strip()
    end_str = str(block.get("end", "")).strip()
    title = str(block.get("title", "Untitled")).strip() or "Untitled"

    if not start_str or not end_str:
        logger.warning(f"Block '{title}': missing start or end time")
        return None

    # Validate and parse time format
    try:
        start_parts = start_str.split(":")
        end_parts = end_str.split(":")

        if len(start_parts) < 2 or len(end_parts) < 2:
            logger.warning(f"Block '{title}': invalid time format (start='{start_str}', end='{end_str}')")
            return None

        start_hour, start_min = int(start_parts[0]), int(start_parts[1])
        end_hour, end_min = int(end_parts[0]), int(end_parts[1])

        # Validate time ranges
        if not (0 <= start_hour <= 23 and 0 <= start_min <= 59):
            logger.warning(f"Block '{title}': invalid start time {start_hour:02d}:{start_min:02d}")
            return None
        if not (0 <= end_hour <= 23 and 0 <= end_min <= 59):
            logger.warning(f"Block '{title}': invalid end time {end_hour:02d}:{end_min:02d}")
            return None

        return {
            "start_hour": start_hour,
            "start_min": start_min,
            "end_hour": end_hour,
            "end_min": end_min,
            "title": title,
            "domain": str(block.get("domain", "")).strip(),
            "task_id": str(block.get("task_id", "")).strip(),
        }

    except (ValueError, IndexError) as e:
        logger.warning(f"Block '{title}': invalid time format - {e}")
        return None


def push_day_plan(
    blocks: List[Dict[str, str]],
    date: dt.date,
    calendar_id: str = "primary",
    max_concurrent: int = 10,
) -> List[str]:
    """Batch-create calendar events from time blocks.

    Each block should have: start (HH:MM), end (HH:MM), title, domain, task_id.
    Clears existing [life-os] events for the date first.
    Returns list of created event IDs.

    Args:
        blocks: List of time block dictionaries
        date: Date to create events for
        calendar_id: Google Calendar ID
        max_concurrent: Maximum number of concurrent event creations
    """
    if not blocks:
        logger.warning(f"No blocks provided for {date}")
        return []

    if not isinstance(blocks, list):
        logger.error(f"Blocks must be a list, got {type(blocks)}")
        return []

    # Validate date is not too far in the future (prevent accidental bulk creation)
    max_future_days = 90
    if (date - dt.date.today()).days > max_future_days:
        logger.warning(f"Date {date} is more than {max_future_days} days in the future")

    logger.info(f"Processing {len(blocks)} time blocks for {date}")

    # Clear existing life-os events first
    try:
        cleared = clear_life_os_events(date, calendar_id=calendar_id)
        if cleared:
            logger.info(f"Cleared {cleared} existing {LIFE_OS_TAG} events for {date}")
    except Exception as e:
        logger.error(f"Failed to clear existing events for {date}: {e}")
        # Continue anyway - better to have duplicate events than no events

    # Validate and process blocks
    valid_blocks = []
    skipped_blocks = 0

    for i, block in enumerate(blocks):
        validated = _validate_time_block(block)
        if validated:
            validated["index"] = i
            valid_blocks.append(validated)
        else:
            skipped_blocks += 1

    if not valid_blocks:
        logger.error(f"No valid time blocks found for {date}")
        return []

    # Create events with error tracking
    created_ids = []
    failed_blocks = []

    for block in valid_blocks:
        try:
            start_dt = dt.datetime(date.year, date.month, date.day,
                                 int(block["start_hour"]), int(block["start_min"]))
            end_dt = dt.datetime(date.year, date.month, date.day,
                               int(block["end_hour"]), int(block["end_min"]))

            # Handle end time on next day if earlier than start time
            if end_dt <= start_dt:
                end_dt += dt.timedelta(days=1)
                logger.info(f"Block '{block['title']}' spans midnight, end time adjusted to next day")

            # Build event details
            summary = f"[{block['domain']}] {block['title']}" if block['domain'] else block['title']
            desc_parts = [LIFE_OS_TAG, "Source: auto_planner"]
            if block['task_id']:
                desc_parts.append(f"Task: {block['task_id']}")
            description = "\n".join(desc_parts)

            # Create the event
            event_id = create_event(
                summary=summary,
                start_dt=start_dt,
                end_dt=end_dt,
                description=description,
                calendar_id=calendar_id,
            )

            if event_id:
                created_ids.append(event_id)
            else:
                failed_blocks.append(block)

        except Exception as e:
            logger.error(f"Unexpected error creating event for block '{block['title']}': {e}")
            failed_blocks.append(block)

    # Log comprehensive summary
    total_blocks = len(blocks)
    successful_blocks = len(created_ids)
    failed_count = len(failed_blocks)

    if successful_blocks > 0:
        logger.info(f"Successfully created {successful_blocks} calendar events for {date}")

    if skipped_blocks > 0:
        logger.warning(f"Skipped {skipped_blocks} blocks due to invalid format")

    if failed_count > 0:
        logger.error(f"Failed to create {failed_count} events")
        for block in failed_blocks[:3]:  # Log first 3 failures for debugging
            logger.error(f"  Failed block: {block['title']} ({block['start_hour']:02d}:{block['start_min']:02d}-{block['end_hour']:02d}:{block['end_min']:02d})")

    logger.info(f"Day plan push completed: {successful_blocks}/{total_blocks} created, {skipped_blocks} skipped, {failed_count} failed")

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
