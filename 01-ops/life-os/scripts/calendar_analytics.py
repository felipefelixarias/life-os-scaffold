#!/usr/bin/env python3
"""Analytics for ``calendar_events.csv``.

Produces per-source and aggregate statistics so commands like ``/status``,
``/daily``, and ``/weekly-review`` can surface meeting load directly instead of
re-deriving it from prompts. Stdlib-only, pairs with the other per-canonical
analytics modules (habit / goal / time / task / project).

CLI:
    python3 calendar_analytics.py [--csv PATH] [--today YYYY-MM-DD]

Library:
    load_calendar_events(path)            -> list[CalendarEvent]
    event_duration_minutes(event)         -> int
    compute_source_stats(source, events, anchor_date) -> SourceStats
    analyze(csv_path, today=None)         -> CalendarReport
    format_duration(mins)                 -> str
    format_report(report)                 -> str
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CSV = (
    REPO_ROOT / "01-ops" / "life-os" / "data" / "canonical" / "calendar_events.csv"
)

MONTH_WINDOW_DAYS = 30
MINUTES_PER_DAY = 24 * 60
UNKNOWN_SOURCE = "unknown"
WEEKDAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


@dataclass(frozen=True)
class CalendarEvent:
    event_id: str
    date: dt.date
    start_time: dt.time
    end_time: dt.time
    title: str
    location: str | None = None
    attendees: tuple[str, ...] = ()
    source: str | None = None
    calendar: str | None = None
    notes: str | None = None


@dataclass
class SourceStats:
    source: str
    today_events: int = 0
    today_minutes: int = 0
    week_events: int = 0
    week_minutes: int = 0
    month_events: int = 0
    month_minutes: int = 0
    unique_calendars: int = 0
    top_location: str | None = None
    top_location_count: int = 0


@dataclass
class CalendarReport:
    anchor_date: dt.date
    week_start: dt.date
    month_start: dt.date
    sources: list[SourceStats] = field(default_factory=list)
    total_events_today: int = 0
    total_minutes_today: int = 0
    total_events_week: int = 0
    total_minutes_week: int = 0
    total_events_month: int = 0
    total_minutes_month: int = 0
    busiest_weekday: str | None = None
    busiest_weekday_minutes: int = 0
    events_per_day_avg: float = 0.0
    top_location: str | None = None
    top_location_count: int = 0
    top_calendar: str | None = None
    top_calendar_count: int = 0


def _parse_attendees(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def _maybe(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def load_calendar_events(path: Path) -> list[CalendarEvent]:
    """Parse ``calendar_events.csv`` into typed events.

    Blank rows (no ``event_id``) are skipped, matching the tolerance of the
    other canonical CSV loaders. Rows with malformed dates or times raise
    ``ValueError`` so bad data surfaces instead of being silently dropped.
    """
    events: list[CalendarEvent] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            event_id = (row.get("event_id") or "").strip()
            if not event_id:
                continue
            events.append(
                CalendarEvent(
                    event_id=event_id,
                    date=dt.date.fromisoformat(row["date"].strip()),
                    start_time=dt.time.fromisoformat(row["start_time"].strip()),
                    end_time=dt.time.fromisoformat(row["end_time"].strip()),
                    title=(row.get("title") or "").strip(),
                    location=_maybe(row.get("location")),
                    attendees=_parse_attendees(row.get("attendees")),
                    source=_maybe(row.get("source")),
                    calendar=_maybe(row.get("calendar")),
                    notes=_maybe(row.get("notes")),
                )
            )
    return events


def event_duration_minutes(event: CalendarEvent) -> int:
    """Minutes between ``start_time`` and ``end_time``.

    Events that end before they start (crossing midnight) are treated as
    wrapping to the next day. Returns 0 for zero-length events rather than a
    negative number.
    """
    start = event.start_time.hour * 60 + event.start_time.minute
    end = event.end_time.hour * 60 + event.end_time.minute
    delta = end - start
    if delta < 0:
        delta += MINUTES_PER_DAY
    return delta


def _iso_week_start(anchor: dt.date) -> dt.date:
    return anchor - dt.timedelta(days=anchor.weekday())


def _month_start(anchor: dt.date) -> dt.date:
    return anchor - dt.timedelta(days=MONTH_WINDOW_DAYS - 1)


def _source_of(event: CalendarEvent) -> str:
    return event.source or UNKNOWN_SOURCE


def compute_source_stats(
    source: str,
    events: list[CalendarEvent],
    anchor_date: dt.date,
) -> SourceStats:
    """Roll up events for a single source to today/week/month windows.

    Only events with matching ``source`` are considered (``None``/empty maps
    to ``UNKNOWN_SOURCE``). The anchor is treated as "today" so callers can
    reproduce reports deterministically for historical dates.
    """
    stats = SourceStats(source=source)
    week_start = _iso_week_start(anchor_date)
    month_start = _month_start(anchor_date)
    calendars: set[str] = set()
    locations: Counter[str] = Counter()

    for event in events:
        if _source_of(event) != source:
            continue
        minutes = event_duration_minutes(event)
        if event.date == anchor_date:
            stats.today_events += 1
            stats.today_minutes += minutes
        if week_start <= event.date <= anchor_date:
            stats.week_events += 1
            stats.week_minutes += minutes
        if month_start <= event.date <= anchor_date:
            stats.month_events += 1
            stats.month_minutes += minutes
            if event.calendar:
                calendars.add(event.calendar)
            if event.location:
                locations[event.location] += 1

    stats.unique_calendars = len(calendars)
    if locations:
        top_loc, top_count = locations.most_common(1)[0]
        stats.top_location = top_loc
        stats.top_location_count = top_count
    return stats


def _busiest_weekday(
    events: list[CalendarEvent],
    month_start: dt.date,
    anchor_date: dt.date,
) -> tuple[str | None, int]:
    by_weekday: list[int] = [0] * 7
    for event in events:
        if month_start <= event.date <= anchor_date:
            by_weekday[event.date.weekday()] += event_duration_minutes(event)
    peak = max(by_weekday)
    if peak == 0:
        return None, 0
    return WEEKDAY_NAMES[by_weekday.index(peak)], peak


def analyze(csv_path: Path, today: dt.date | None = None) -> CalendarReport:
    """Build a ``CalendarReport`` from ``calendar_events.csv``.

    ``today`` is the anchor used for today/week/month windows; it defaults to
    the system date. A missing or empty CSV yields a report with all zero
    counters (rather than raising), so callers can render "nothing scheduled"
    gracefully.
    """
    anchor = today or dt.date.today()
    week_start = _iso_week_start(anchor)
    month_start = _month_start(anchor)

    events = load_calendar_events(csv_path) if csv_path.exists() else []

    sources = sorted({_source_of(event) for event in events})
    source_stats = [compute_source_stats(src, events, anchor) for src in sources]

    report = CalendarReport(
        anchor_date=anchor,
        week_start=week_start,
        month_start=month_start,
        sources=source_stats,
    )

    month_locations: Counter[str] = Counter()
    month_calendars: Counter[str] = Counter()
    month_days: set[dt.date] = set()

    for event in events:
        minutes = event_duration_minutes(event)
        if event.date == anchor:
            report.total_events_today += 1
            report.total_minutes_today += minutes
        if week_start <= event.date <= anchor:
            report.total_events_week += 1
            report.total_minutes_week += minutes
        if month_start <= event.date <= anchor:
            report.total_events_month += 1
            report.total_minutes_month += minutes
            month_days.add(event.date)
            if event.location:
                month_locations[event.location] += 1
            if event.calendar:
                month_calendars[event.calendar] += 1

    if month_days:
        report.events_per_day_avg = report.total_events_month / len(month_days)

    report.busiest_weekday, report.busiest_weekday_minutes = _busiest_weekday(
        events, month_start, anchor
    )

    if month_locations:
        loc, count = month_locations.most_common(1)[0]
        report.top_location = loc
        report.top_location_count = count
    if month_calendars:
        cal, count = month_calendars.most_common(1)[0]
        report.top_calendar = cal
        report.top_calendar_count = count

    return report


def format_duration(minutes: int) -> str:
    """Render a minute count as ``"Xh YYm"`` / ``"Xh"`` / ``"YYm"``."""
    if minutes <= 0:
        return "0m"
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours}h {mins:02d}m"
    if hours:
        return f"{hours}h"
    return f"{mins}m"


def format_report(report: CalendarReport) -> str:
    lines: list[str] = []
    lines.append(f"Calendar Analytics — anchor {report.anchor_date.isoformat()}")
    lines.append(
        f"  Week: {report.week_start.isoformat()} → {report.anchor_date.isoformat()}"
    )
    lines.append(
        f"  Month: {report.month_start.isoformat()} → {report.anchor_date.isoformat()}"
    )
    lines.append("")
    lines.append(
        f"Today: {report.total_events_today} events, "
        f"{format_duration(report.total_minutes_today)}"
    )
    lines.append(
        f"Week:  {report.total_events_week} events, "
        f"{format_duration(report.total_minutes_week)}"
    )
    lines.append(
        f"Month: {report.total_events_month} events, "
        f"{format_duration(report.total_minutes_month)} "
        f"(avg {report.events_per_day_avg:.1f}/active-day)"
    )

    if report.busiest_weekday:
        lines.append(
            f"Busiest weekday (last 30d): {report.busiest_weekday} "
            f"({format_duration(report.busiest_weekday_minutes)})"
        )
    if report.top_location:
        lines.append(
            f"Top location (last 30d): {report.top_location} "
            f"({report.top_location_count})"
        )
    if report.top_calendar:
        lines.append(
            f"Top calendar (last 30d): {report.top_calendar} "
            f"({report.top_calendar_count})"
        )

    if report.sources:
        lines.append("")
        lines.append(
            f"{'source':<16} {'today':>10} {'week':>10} {'month':>10} {'cals':>6}"
        )
        lines.append("-" * 56)
        for s in report.sources:
            lines.append(
                f"{s.source:<16} "
                f"{s.today_events:>3} ({format_duration(s.today_minutes):>5}) "
                f"{s.week_events:>3} ({format_duration(s.week_minutes):>5}) "
                f"{s.month_events:>3} ({format_duration(s.month_minutes):>5}) "
                f"{s.unique_calendars:>6}"
            )
    else:
        lines.append("")
        lines.append("(no events found)")

    return "\n".join(lines)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV,
        help=f"path to calendar_events.csv (default: {DEFAULT_CSV})",
    )
    parser.add_argument(
        "--today",
        type=dt.date.fromisoformat,
        default=None,
        help="override anchor date (YYYY-MM-DD); default is today",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    report = analyze(args.csv, today=args.today)
    print(format_report(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
