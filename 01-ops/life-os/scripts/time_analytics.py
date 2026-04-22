#!/usr/bin/env python3
"""Time tracking analytics: domain rollups, weekly/monthly totals, planned vs logged.

Reads ``time_logs.csv`` and ``time_blocks.csv`` and produces per-domain statistics:
minutes logged today, this ISO week, and in the last 30 days, plus adherence to
time blocks planned for the current week. Run as a script to print a formatted
summary table; import the helpers to feed the ``/status``, ``/daily``, and
``/weekly-review`` commands.
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TIME_LOGS_CSV = (
    REPO_ROOT / "01-ops" / "life-os" / "data" / "canonical" / "time_logs.csv"
)
TIME_BLOCKS_CSV = (
    REPO_ROOT / "01-ops" / "life-os" / "data" / "canonical" / "time_blocks.csv"
)

MONTH_WINDOW_DAYS = 30
UNASSIGNED_DOMAIN = "unassigned"


@dataclass(frozen=True)
class TimeLog:
    """A single row from ``time_logs.csv`` reduced to the analytics-relevant fields."""

    entry_date: date
    activity: str
    domain: str
    duration_mins: int


@dataclass(frozen=True)
class TimeBlock:
    """A scheduled block from ``time_blocks.csv`` with a resolved duration."""

    entry_date: date
    start: time
    end: time
    title: str
    domain: str
    status: str
    duration_mins: int


@dataclass(frozen=True)
class DomainStats:
    """Computed time analytics for a single domain."""

    domain: str
    today_mins: int
    week_mins: int
    month_mins: int
    total_mins: int
    unique_activities: int
    top_activity: str | None
    top_activity_mins: int
    planned_week_mins: int
    week_adherence: float | None  # None when nothing was planned for the week


@dataclass(frozen=True)
class TimeReport:
    """Aggregate view across all domains for the anchor date."""

    anchor: date
    domain_stats: list[DomainStats]
    total_today_mins: int
    total_week_mins: int
    total_month_mins: int
    active_days_last_30: int


def _parse_int(raw: str) -> int | None:
    raw = raw.strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def _parse_time(raw: str) -> time | None:
    raw = raw.strip()
    if not raw:
        return None
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).time()
        except ValueError:
            continue
    return None


def _parse_date(raw: str) -> date | None:
    raw = raw.strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _domain_of(raw: str | None) -> str:
    """Normalize the domain column: blanks bucket into ``UNASSIGNED_DOMAIN``."""
    if raw is None:
        return UNASSIGNED_DOMAIN
    cleaned = raw.strip()
    return cleaned if cleaned else UNASSIGNED_DOMAIN


def _duration_between(start: time, end: time) -> int:
    """Return whole minutes between two same-day times. Negative spans yield 0."""
    start_mins = start.hour * 60 + start.minute
    end_mins = end.hour * 60 + end.minute
    return max(0, end_mins - start_mins)


def load_time_logs(path: Path = TIME_LOGS_CSV) -> list[TimeLog]:
    """Load time log rows. Silently skips malformed or zero-duration entries.

    When ``duration_mins`` is absent but ``start_time``/``end_time`` are present,
    the duration is computed from the span so user-friendly logs aren't dropped.
    """
    logs: list[TimeLog] = []
    if not path.exists():
        return logs
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entry_date = _parse_date(row.get("date", ""))
            activity = (row.get("activity") or "").strip()
            if entry_date is None or not activity:
                continue
            duration = _parse_int(row.get("duration_mins", ""))
            if duration is None:
                start = _parse_time(row.get("start_time", ""))
                end = _parse_time(row.get("end_time", ""))
                if start is not None and end is not None:
                    duration = _duration_between(start, end) or None
            if duration is None:
                continue
            logs.append(
                TimeLog(
                    entry_date=entry_date,
                    activity=activity,
                    domain=_domain_of(row.get("domain")),
                    duration_mins=duration,
                )
            )
    return logs


def load_time_blocks(path: Path = TIME_BLOCKS_CSV) -> list[TimeBlock]:
    """Load time blocks. Silently skips rows missing date, start, or end."""
    blocks: list[TimeBlock] = []
    if not path.exists():
        return blocks
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entry_date = _parse_date(row.get("date", ""))
            start = _parse_time(row.get("start", ""))
            end = _parse_time(row.get("end", ""))
            if entry_date is None or start is None or end is None:
                continue
            duration = _duration_between(start, end)
            if duration == 0:
                continue
            blocks.append(
                TimeBlock(
                    entry_date=entry_date,
                    start=start,
                    end=end,
                    title=(row.get("title") or "").strip(),
                    domain=_domain_of(row.get("domain")),
                    status=(row.get("status") or "").strip().lower(),
                    duration_mins=duration,
                )
            )
    return blocks


def _week_start(anchor: date) -> date:
    """Monday of the ISO week containing ``anchor``."""
    return anchor - timedelta(days=anchor.weekday())


def _top_activity(logs: list[TimeLog]) -> tuple[str | None, int]:
    """Return (activity_name, total_mins) for the activity with most minutes."""
    totals: dict[str, int] = {}
    for log in logs:
        totals[log.activity] = totals.get(log.activity, 0) + log.duration_mins
    if not totals:
        return (None, 0)
    # Sort by (-mins, name) so ties break alphabetically — deterministic reports.
    name, mins = min(totals.items(), key=lambda kv: (-kv[1], kv[0].lower()))
    return (name, mins)


def compute_domain_stats(
    domain: str,
    logs: list[TimeLog],
    blocks: list[TimeBlock],
    today: date,
) -> DomainStats:
    """Compute analytics for a single domain across the anchor date's windows."""
    domain_logs = [log for log in logs if log.domain == domain]
    domain_blocks = [block for block in blocks if block.domain == domain]

    week_start = _week_start(today)
    month_start = today - timedelta(days=MONTH_WINDOW_DAYS - 1)

    today_mins = sum(
        log.duration_mins for log in domain_logs if log.entry_date == today
    )
    week_mins = sum(
        log.duration_mins
        for log in domain_logs
        if week_start <= log.entry_date <= today
    )
    month_mins = sum(
        log.duration_mins
        for log in domain_logs
        if month_start <= log.entry_date <= today
    )
    total_mins = sum(log.duration_mins for log in domain_logs)

    activities = {log.activity for log in domain_logs}
    top_name, top_mins = _top_activity(domain_logs)

    week_end = week_start + timedelta(days=6)
    planned_week = sum(
        block.duration_mins
        for block in domain_blocks
        if week_start <= block.entry_date <= week_end
    )
    adherence = None if planned_week == 0 else week_mins / planned_week

    return DomainStats(
        domain=domain,
        today_mins=today_mins,
        week_mins=week_mins,
        month_mins=month_mins,
        total_mins=total_mins,
        unique_activities=len(activities),
        top_activity=top_name,
        top_activity_mins=top_mins,
        planned_week_mins=planned_week,
        week_adherence=adherence,
    )


def analyze(
    logs_path: Path = TIME_LOGS_CSV,
    blocks_path: Path = TIME_BLOCKS_CSV,
    today: date | None = None,
) -> TimeReport:
    """Load time data and compute per-domain stats plus an aggregate view.

    Domains are drawn from both logs and blocks — planned-but-unlogged and
    logged-but-unplanned domains both surface in the report. Results are sorted
    by descending 30-day total, then alphabetically, so the most-used domains
    appear first.
    """
    logs = load_time_logs(logs_path)
    blocks = load_time_blocks(blocks_path)
    anchor = today or date.today()

    domains: set[str] = {log.domain for log in logs} | {
        block.domain for block in blocks
    }
    stats = [compute_domain_stats(d, logs, blocks, anchor) for d in domains]
    stats.sort(key=lambda s: (-s.month_mins, s.domain.lower()))

    month_start = anchor - timedelta(days=MONTH_WINDOW_DAYS - 1)
    active_days = len(
        {log.entry_date for log in logs if month_start <= log.entry_date <= anchor}
    )

    return TimeReport(
        anchor=anchor,
        domain_stats=stats,
        total_today_mins=sum(s.today_mins for s in stats),
        total_week_mins=sum(s.week_mins for s in stats),
        total_month_mins=sum(s.month_mins for s in stats),
        active_days_last_30=active_days,
    )


def format_duration(mins: int) -> str:
    """Render minutes as ``Xh Ym`` (or ``Xm`` for sub-hour spans, ``-`` for zero)."""
    if mins <= 0:
        return "-"
    hours, remainder = divmod(mins, 60)
    if hours == 0:
        return f"{remainder}m"
    if remainder == 0:
        return f"{hours}h"
    return f"{hours}h {remainder}m"


def _format_adherence(adherence: float | None) -> str:
    if adherence is None:
        return "-"
    return f"{round(adherence * 100)}%"


def format_report(report: TimeReport) -> str:
    """Render a compact, human-readable table of time analytics."""
    if not report.domain_stats:
        return "No time logs or blocks found.\n"

    header = (
        f"{'Domain':<14} {'Today':>7} {'Week':>8} {'Month':>9} "
        f"{'Planned':>9} {'Adherence':>10} {'Top activity':<24}"
    )
    sep = "-" * len(header)
    lines = [header, sep]
    for s in report.domain_stats:
        top = (s.top_activity or "-")[:24]
        lines.append(
            f"{s.domain[:14]:<14} {format_duration(s.today_mins):>7} "
            f"{format_duration(s.week_mins):>8} {format_duration(s.month_mins):>9} "
            f"{format_duration(s.planned_week_mins):>9} "
            f"{_format_adherence(s.week_adherence):>10} {top:<24}"
        )
    lines.append(sep)
    lines.append(
        f"{'TOTAL':<14} {format_duration(report.total_today_mins):>7} "
        f"{format_duration(report.total_week_mins):>8} "
        f"{format_duration(report.total_month_mins):>9}"
    )
    lines.append(
        f"Active days in last {MONTH_WINDOW_DAYS}: "
        f"{report.active_days_last_30}/{MONTH_WINDOW_DAYS}"
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Print a formatted time analytics report."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--logs",
        type=Path,
        default=TIME_LOGS_CSV,
        help="Path to time_logs.csv (default: canonical location).",
    )
    parser.add_argument(
        "--blocks",
        type=Path,
        default=TIME_BLOCKS_CSV,
        help="Path to time_blocks.csv (default: canonical location).",
    )
    parser.add_argument(
        "--today",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=None,
        help="Override 'today' as YYYY-MM-DD (useful for deterministic reports).",
    )
    args = parser.parse_args(argv)

    report = analyze(
        logs_path=args.logs,
        blocks_path=args.blocks,
        today=args.today,
    )
    sys.stdout.write(format_report(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
