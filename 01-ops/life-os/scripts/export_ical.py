#!/usr/bin/env python3
"""Export canonical CSV data to RFC 5545 iCalendar (.ics) format.

This is the *export* counterpart to ``fetch_calendar_feeds.py`` (which imports
iCal feeds). It converts rows from ``time_blocks.csv`` and/or
``calendar_events.csv`` into a portable ``.ics`` file that can be imported by
any calendar client (iOS Calendar, Outlook, Thunderbird, Fastmail, etc.).

The generator uses only the Python standard library and emits times as UTC
(``...Z``), so no ``VTIMEZONE`` block is needed and the output is timezone-safe
on every importer.

CLI:
    python3 export_ical.py --source time_blocks
    python3 export_ical.py --source calendar_events --output events.ics
    python3 export_ical.py --source both --start-date 2026-01-01 --end-date 2026-12-31

Exit codes:
    0 success (file written or content printed)
    1 runtime error (unreadable CSV, invalid dates, no rows)
    2 invalid CLI arguments
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import logging
import sys
from pathlib import Path
from typing import Any, TextIO
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
CANONICAL_DIR = REPO_ROOT / "01-ops" / "life-os" / "data" / "canonical"
PROFILE_PATH = REPO_ROOT / "01-ops" / "life-os" / "config" / "profile.json"

TIME_BLOCKS_CSV = CANONICAL_DIR / "time_blocks.csv"
CALENDAR_EVENTS_CSV = CANONICAL_DIR / "calendar_events.csv"

PRODID = "-//life-os//export_ical//EN"
DEFAULT_TIMEZONE = "America/Los_Angeles"
UID_DOMAIN = "life-os"

# RFC 5545 §3.1 requires content lines to be folded at 75 octets.
MAX_LINE_OCTETS = 75


def load_timezone(profile_path: Path = PROFILE_PATH) -> ZoneInfo:
    """Return the user's configured timezone, falling back to the default."""
    tz_name = DEFAULT_TIMEZONE
    try:
        with profile_path.open("r", encoding="utf-8") as f:
            tz_name = json.load(f).get("timezone", DEFAULT_TIMEZONE)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        logger.warning(
            "Unknown timezone %r; falling back to %s", tz_name, DEFAULT_TIMEZONE
        )
        return ZoneInfo(DEFAULT_TIMEZONE)


def _parse_time(value: str) -> dt.time:
    """Parse HH:MM or HH:MM:SS into a ``datetime.time``."""
    return dt.time.fromisoformat(value)


def _parse_date(value: str) -> dt.date:
    """Parse YYYY-MM-DD into a ``datetime.date``."""
    return dt.date.fromisoformat(value)


def _combine_utc(day: dt.date, when: dt.time, tz: ZoneInfo) -> dt.datetime:
    """Combine a date and time in the user's tz, then convert to UTC."""
    local = dt.datetime.combine(day, when, tzinfo=tz)
    return local.astimezone(dt.UTC)


def _format_utc(moment: dt.datetime) -> str:
    """Format a UTC datetime as RFC 5545 ``YYYYMMDDTHHMMSSZ``."""
    if moment.tzinfo is None or moment.utcoffset() != dt.timedelta(0):
        moment = moment.astimezone(dt.UTC)
    return moment.strftime("%Y%m%dT%H%M%SZ")


def escape_text(value: str) -> str:
    """Escape TEXT property values per RFC 5545 §3.3.11.

    Backslash must be escaped first (otherwise we'd double-escape our own
    replacements). Newlines become literal ``\\n``.
    """
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )


def fold_line(line: str) -> str:
    """Fold a content line at 75 octets per RFC 5545 §3.1.

    Continuation lines begin with a single space. Folding is byte-accurate
    because UTF-8 characters must not be split mid-codepoint.
    """
    encoded = line.encode("utf-8")
    if len(encoded) <= MAX_LINE_OCTETS:
        return line

    parts: list[str] = []
    remaining = encoded
    limit = MAX_LINE_OCTETS
    while len(remaining) > limit:
        cut = limit
        # Don't split a multi-byte UTF-8 sequence (continuation bytes are 10xxxxxx).
        while cut > 0 and (remaining[cut] & 0xC0) == 0x80:
            cut -= 1
        parts.append(remaining[:cut].decode("utf-8"))
        remaining = remaining[cut:]
        # Continuation lines allow one extra octet because the leading space
        # is prepended on the client side; but we keep it simple and use 74.
        limit = MAX_LINE_OCTETS - 1
    parts.append(remaining.decode("utf-8"))
    return parts[0] + "".join(f"\r\n {p}" for p in parts[1:])


def _write_line(out: list[str], line: str) -> None:
    out.append(fold_line(line))


def _row_event_window(
    row: dict[str, str],
    *,
    date_col: str,
    start_col: str,
    end_col: str,
    tz: ZoneInfo,
) -> tuple[dt.datetime, dt.datetime] | None:
    """Parse a row's date + start/end into UTC datetimes, or ``None`` on error.

    Rows missing either time receive a 1-hour default window — skipping them
    would silently drop data, and raising would abort the whole export.
    """
    raw_date = (row.get(date_col) or "").strip()
    raw_start = (row.get(start_col) or "").strip()
    raw_end = (row.get(end_col) or "").strip()
    if not raw_date:
        return None
    try:
        day = _parse_date(raw_date)
    except ValueError:
        logger.warning("Skipping row with invalid date %r", raw_date)
        return None

    try:
        start_t = _parse_time(raw_start) if raw_start else dt.time(0, 0)
    except ValueError:
        logger.warning(
            "Skipping row with invalid start %r for date %s", raw_start, raw_date
        )
        return None

    if raw_end:
        try:
            end_t = _parse_time(raw_end)
        except ValueError:
            logger.warning(
                "Skipping row with invalid end %r for date %s", raw_end, raw_date
            )
            return None
    else:
        end_t = dt.time(min(start_t.hour + 1, 23), start_t.minute)

    start_utc = _combine_utc(day, start_t, tz)
    end_utc = _combine_utc(day, end_t, tz)
    if end_utc <= start_utc:
        end_utc = end_utc + dt.timedelta(days=1)
    return start_utc, end_utc


def time_block_to_vevent(
    row: dict[str, str],
    tz: ZoneInfo,
    dtstamp: dt.datetime,
) -> list[str] | None:
    """Convert a ``time_blocks.csv`` row to VEVENT lines, or ``None`` to skip."""
    block_id = (row.get("block_id") or "").strip()
    title = (row.get("title") or "").strip() or "Untitled block"
    if not block_id:
        logger.warning("Skipping time_block row missing block_id: %r", row)
        return None

    window = _row_event_window(
        row, date_col="date", start_col="start", end_col="end", tz=tz
    )
    if window is None:
        return None
    start_utc, end_utc = window

    domain = (row.get("domain") or "").strip()
    task_id = (row.get("task_id") or "").strip()
    source = (row.get("source") or "").strip()
    status = (row.get("status") or "").strip()
    notes = (row.get("notes") or "").strip()

    summary = f"[{domain}] {title}" if domain else title
    desc_parts: list[str] = []
    if task_id:
        desc_parts.append(f"Task: {task_id}")
    if source:
        desc_parts.append(f"Source: {source}")
    if status:
        desc_parts.append(f"Status: {status}")
    if notes:
        desc_parts.append(notes)
    description = "\n".join(desc_parts)

    lines: list[str] = []
    _write_line(lines, "BEGIN:VEVENT")
    _write_line(lines, f"UID:{block_id}@{UID_DOMAIN}")
    _write_line(lines, f"DTSTAMP:{_format_utc(dtstamp)}")
    _write_line(lines, f"DTSTART:{_format_utc(start_utc)}")
    _write_line(lines, f"DTEND:{_format_utc(end_utc)}")
    _write_line(lines, f"SUMMARY:{escape_text(summary)}")
    if description:
        _write_line(lines, f"DESCRIPTION:{escape_text(description)}")
    if domain:
        _write_line(lines, f"CATEGORIES:{escape_text(domain)}")
    _write_line(lines, "END:VEVENT")
    return lines


def calendar_event_to_vevent(
    row: dict[str, str],
    tz: ZoneInfo,
    dtstamp: dt.datetime,
) -> list[str] | None:
    """Convert a ``calendar_events.csv`` row to VEVENT lines, or ``None``."""
    event_id = (row.get("event_id") or "").strip()
    title = (row.get("title") or "").strip() or "Untitled event"
    if not event_id:
        logger.warning("Skipping calendar_events row missing event_id: %r", row)
        return None

    window = _row_event_window(
        row,
        date_col="date",
        start_col="start_time",
        end_col="end_time",
        tz=tz,
    )
    if window is None:
        return None
    start_utc, end_utc = window

    location = (row.get("location") or "").strip()
    attendees = (row.get("attendees") or "").strip()
    source = (row.get("source") or "").strip()
    calendar = (row.get("calendar") or "").strip()
    notes = (row.get("notes") or "").strip()

    desc_parts: list[str] = []
    if attendees:
        desc_parts.append(f"Attendees: {attendees}")
    if calendar:
        desc_parts.append(f"Calendar: {calendar}")
    if source:
        desc_parts.append(f"Source: {source}")
    if notes:
        desc_parts.append(notes)
    description = "\n".join(desc_parts)

    lines: list[str] = []
    _write_line(lines, "BEGIN:VEVENT")
    _write_line(lines, f"UID:{event_id}@{UID_DOMAIN}")
    _write_line(lines, f"DTSTAMP:{_format_utc(dtstamp)}")
    _write_line(lines, f"DTSTART:{_format_utc(start_utc)}")
    _write_line(lines, f"DTEND:{_format_utc(end_utc)}")
    _write_line(lines, f"SUMMARY:{escape_text(title)}")
    if location:
        _write_line(lines, f"LOCATION:{escape_text(location)}")
    if description:
        _write_line(lines, f"DESCRIPTION:{escape_text(description)}")
    _write_line(lines, "END:VEVENT")
    return lines


def _row_date(row: dict[str, str], col: str = "date") -> dt.date | None:
    raw = (row.get(col) or "").strip()
    if not raw:
        return None
    try:
        return _parse_date(raw)
    except ValueError:
        return None


def _in_range(
    row: dict[str, str],
    start: dt.date | None,
    end: dt.date | None,
    date_col: str = "date",
) -> bool:
    if start is None and end is None:
        return True
    day = _row_date(row, date_col)
    if day is None:
        return False
    if start is not None and day < start:
        return False
    return not (end is not None and day > end)


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Source CSV not found: {path}")
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def build_calendar(
    *,
    time_blocks: list[dict[str, str]] | None = None,
    calendar_events: list[dict[str, str]] | None = None,
    tz: ZoneInfo,
    start: dt.date | None = None,
    end: dt.date | None = None,
    now: dt.datetime | None = None,
) -> str:
    """Return the full iCalendar document for the given rows."""
    dtstamp = now or dt.datetime.now(dt.UTC)

    lines: list[str] = []
    _write_line(lines, "BEGIN:VCALENDAR")
    _write_line(lines, "VERSION:2.0")
    _write_line(lines, f"PRODID:{PRODID}")
    _write_line(lines, "CALSCALE:GREGORIAN")
    _write_line(lines, "METHOD:PUBLISH")

    event_count = 0
    for row in time_blocks or []:
        if not _in_range(row, start, end):
            continue
        ev = time_block_to_vevent(row, tz, dtstamp)
        if ev is not None:
            lines.extend(ev)
            event_count += 1

    for row in calendar_events or []:
        if not _in_range(row, start, end):
            continue
        ev = calendar_event_to_vevent(row, tz, dtstamp)
        if ev is not None:
            lines.extend(ev)
            event_count += 1

    _write_line(lines, "END:VCALENDAR")
    logger.info("Wrote %d VEVENT(s) to iCalendar output", event_count)
    return "\r\n".join(lines) + "\r\n"


def export_ical(
    *,
    source: str,
    start: dt.date | None = None,
    end: dt.date | None = None,
    time_blocks_path: Path = TIME_BLOCKS_CSV,
    calendar_events_path: Path = CALENDAR_EVENTS_CSV,
    tz: ZoneInfo | None = None,
    now: dt.datetime | None = None,
) -> str:
    """Read canonical CSV(s) and return the iCalendar document text."""
    if source not in {"time_blocks", "calendar_events", "both"}:
        raise ValueError(f"Unknown source {source!r}")

    tz = tz or load_timezone()

    blocks = _read_csv(time_blocks_path) if source in {"time_blocks", "both"} else None
    events = (
        _read_csv(calendar_events_path)
        if source in {"calendar_events", "both"}
        else None
    )

    return build_calendar(
        time_blocks=blocks,
        calendar_events=events,
        tz=tz,
        start=start,
        end=end,
        now=now,
    )


def _parse_cli_date(value: str) -> dt.date:
    try:
        return _parse_date(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {value!r}") from exc


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export canonical CSV data to RFC 5545 iCalendar format.",
    )
    parser.add_argument(
        "--source",
        choices=["time_blocks", "calendar_events", "both"],
        default="both",
        help="Which canonical CSV to export (default: both).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output .ics file path. If omitted, writes to stdout.",
    )
    parser.add_argument(
        "--start-date",
        type=_parse_cli_date,
        help="Only include events on or after this date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--end-date",
        type=_parse_cli_date,
        help="Only include events on or before this date (YYYY-MM-DD).",
    )
    return parser


def main(argv: list[str] | None = None, stdout: TextIO | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.start_date and args.end_date and args.start_date > args.end_date:
        parser.error("--start-date must be on or before --end-date")

    try:
        document = export_ical(
            source=args.source,
            start=args.start_date,
            end=args.end_date,
            time_blocks_path=TIME_BLOCKS_CSV,
            calendar_events_path=CALENDAR_EVENTS_CSV,
        )
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 1
    except ValueError as exc:
        logger.error("%s", exc)
        return 1

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(document, encoding="utf-8", newline="")
        logger.info("Wrote iCalendar output to %s", args.output)
    else:
        out: Any = stdout if stdout is not None else sys.stdout
        out.write(document)
    return 0


if __name__ == "__main__":
    sys.exit(main())
