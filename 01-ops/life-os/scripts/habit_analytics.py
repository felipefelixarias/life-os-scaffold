#!/usr/bin/env python3
"""Habit streak, adherence, and summary analytics.

Reads ``habits.csv`` and ``daily_log.csv`` and produces per-habit statistics:
current and longest streaks, weekly/monthly adherence, and last-logged dates.
Run as a script to print a formatted summary table; import the helpers to
feed the ``/status``, ``/daily``, and ``/weekly-review`` commands.
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from itertools import pairwise
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
HABITS_CSV = REPO_ROOT / "01-ops" / "life-os" / "data" / "canonical" / "habits.csv"
DAILY_LOG_CSV = REPO_ROOT / "01-ops" / "life-os" / "logs" / "daily_log.csv"

MONTH_WINDOW_DAYS = 30


@dataclass(frozen=True)
class Habit:
    """A habit definition from ``habits.csv``."""

    habit_id: str
    area: str
    name: str
    frequency: str  # "daily" or "weekly"
    target_per_week: int
    min_value: float | None
    unit: str | None
    active: bool


@dataclass(frozen=True)
class LogEntry:
    """A single entry from ``daily_log.csv``."""

    entry_date: date
    habit_id: str
    value: float | None  # numeric value, or None if non-numeric


@dataclass(frozen=True)
class HabitStats:
    """Computed analytics for a single habit over a given window."""

    habit: Habit
    current_streak: int
    longest_streak: int
    week_completed: int
    week_target: int
    week_adherence: float
    month_completed: int
    month_target: int
    month_adherence: float
    last_logged: date | None


def _parse_bool(raw: str) -> bool:
    return raw.strip().lower() in {"true", "1", "yes", "y"}


def _parse_float(raw: str) -> float | None:
    raw = raw.strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_int(raw: str, default: int) -> int:
    raw = raw.strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def load_habits(path: Path = HABITS_CSV) -> list[Habit]:
    """Load habit definitions. Silently skips malformed rows."""
    habits: list[Habit] = []
    if not path.exists():
        return habits
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            habit_id = (row.get("habit_id") or "").strip()
            if not habit_id:
                continue
            habits.append(
                Habit(
                    habit_id=habit_id,
                    area=(row.get("area") or "").strip(),
                    name=(row.get("name") or habit_id).strip(),
                    frequency=(row.get("frequency") or "daily").strip().lower(),
                    target_per_week=_parse_int(row.get("target_per_week", ""), 7),
                    min_value=_parse_float(row.get("min_value", "")),
                    unit=(row.get("unit") or "").strip() or None,
                    active=_parse_bool(row.get("active", "true")),
                )
            )
    return habits


def load_daily_log(path: Path = DAILY_LOG_CSV) -> list[LogEntry]:
    """Load daily log entries. Silently skips rows with unparseable dates."""
    entries: list[LogEntry] = []
    if not path.exists():
        return entries
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_date = (row.get("date") or "").strip()
            habit_id = (row.get("habit_id") or "").strip()
            if not raw_date or not habit_id:
                continue
            try:
                entry_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
            except ValueError:
                continue
            entries.append(
                LogEntry(
                    entry_date=entry_date,
                    habit_id=habit_id,
                    value=_parse_float(row.get("value", "")),
                )
            )
    return entries


def is_completion(entry: LogEntry, habit: Habit) -> bool:
    """Return True if the entry counts as a completion for the habit.

    A log entry is a completion when:
    - The habit has no ``min_value`` threshold, or
    - The entry's numeric value meets or exceeds ``min_value``.

    Non-numeric values count as completions only when no threshold is set.
    """
    if habit.min_value is None:
        return True
    if entry.value is None:
        return False
    return entry.value >= habit.min_value


def _completion_dates(habit: Habit, entries: list[LogEntry]) -> set[date]:
    """Return the set of dates on which the habit was completed."""
    return {
        e.entry_date
        for e in entries
        if e.habit_id == habit.habit_id and is_completion(e, habit)
    }


def _current_streak(completions: set[date], today: date) -> int:
    """Consecutive days up to (and including) today where habit was completed.

    If today is missing but yesterday is present, the streak is measured up to
    yesterday — today's log may simply not be recorded yet. If both today and
    yesterday are missing, the streak is 0.
    """
    if today in completions:
        cursor = today
    elif (today - timedelta(days=1)) in completions:
        cursor = today - timedelta(days=1)
    else:
        return 0
    streak = 0
    while cursor in completions:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def _longest_streak(completions: set[date]) -> int:
    """Longest run of consecutive completion days anywhere in history."""
    if not completions:
        return 0
    sorted_dates = sorted(completions)
    longest = 1
    run = 1
    for prev, curr in pairwise(sorted_dates):
        if (curr - prev).days == 1:
            run += 1
            longest = max(longest, run)
        else:
            run = 1
    return longest


def _adherence(completed: int, target: int) -> float:
    """Completed / target, clamped to [0.0, 1.0]. Zero target returns 1.0."""
    if target <= 0:
        return 1.0
    return min(1.0, completed / target)


def compute_stats(habit: Habit, entries: list[LogEntry], today: date) -> HabitStats:
    """Compute analytics for a single habit."""
    completions = _completion_dates(habit, entries)

    current = _current_streak(completions, today)
    longest = _longest_streak(completions)

    week_start = today - timedelta(days=today.weekday())  # Monday
    week_completed = sum(1 for d in completions if week_start <= d <= today)

    month_start = today - timedelta(days=MONTH_WINDOW_DAYS - 1)
    month_completed = sum(1 for d in completions if month_start <= d <= today)

    week_target = min(7, max(0, habit.target_per_week))
    # Scale weekly target to the 30-day window, rounding to nearest integer.
    month_target = round(week_target * MONTH_WINDOW_DAYS / 7)

    last_logged = max(completions) if completions else None

    return HabitStats(
        habit=habit,
        current_streak=current,
        longest_streak=longest,
        week_completed=week_completed,
        week_target=week_target,
        week_adherence=_adherence(week_completed, week_target),
        month_completed=month_completed,
        month_target=month_target,
        month_adherence=_adherence(month_completed, month_target),
        last_logged=last_logged,
    )


def analyze(
    habits_path: Path = HABITS_CSV,
    log_path: Path = DAILY_LOG_CSV,
    today: date | None = None,
    include_inactive: bool = False,
) -> list[HabitStats]:
    """Load data and compute stats for each habit.

    Results are sorted by active-first, then descending current streak, then
    habit name — putting the most-engaged habits at the top of reports.
    """
    habits = load_habits(habits_path)
    entries = load_daily_log(log_path)
    anchor = today or date.today()

    selected = [h for h in habits if h.active or include_inactive]
    stats = [compute_stats(h, entries, anchor) for h in selected]
    stats.sort(
        key=lambda s: (not s.habit.active, -s.current_streak, s.habit.name.lower())
    )
    return stats


def format_report(stats: list[HabitStats]) -> str:
    """Render a compact, human-readable table of habit stats."""
    if not stats:
        return "No active habits found.\n"

    header = (
        f"{'Habit':<22} {'Area':<10} {'Streak':>7} {'Best':>5} "
        f"{'Week':>8} {'Month':>9} {'Last logged':>12}"
    )
    sep = "-" * len(header)
    lines = [header, sep]
    for s in stats:
        week = f"{s.week_completed}/{s.week_target}"
        month = f"{s.month_completed}/{s.month_target}"
        last = s.last_logged.isoformat() if s.last_logged else "never"
        name = s.habit.name[:22]
        area = s.habit.area[:10]
        lines.append(
            f"{name:<22} {area:<10} {s.current_streak:>7} {s.longest_streak:>5} "
            f"{week:>8} {month:>9} {last:>12}"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Print a formatted habit analytics report."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--habits",
        type=Path,
        default=HABITS_CSV,
        help="Path to habits.csv (default: canonical location).",
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=DAILY_LOG_CSV,
        help="Path to daily_log.csv (default: canonical location).",
    )
    parser.add_argument(
        "--today",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=None,
        help="Override 'today' as YYYY-MM-DD (useful for deterministic reports).",
    )
    parser.add_argument(
        "--include-inactive",
        action="store_true",
        help="Include habits marked active=false in the report.",
    )
    args = parser.parse_args(argv)

    stats = analyze(
        habits_path=args.habits,
        log_path=args.log,
        today=args.today,
        include_inactive=args.include_inactive,
    )
    sys.stdout.write(format_report(stats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
