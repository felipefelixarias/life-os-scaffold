#!/usr/bin/env python3
"""Goal progress, pacing, and on-track analytics.

Reads ``goals.csv`` and produces per-goal statistics: progress percent
against the metric target, days remaining until ``target_date``, expected
linear progress for the horizon, and an on-track verdict. Run as a script
to print a summary table; import the helpers to feed ``/status``,
``/weekly-review``, and the goal-tracking commands.
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
GOALS_CSV = REPO_ROOT / "01-ops" / "life-os" / "data" / "canonical" / "goals.csv"

HORIZON_DAYS: dict[str, int] = {"month": 30, "quarter": 90, "year": 365}


@dataclass(frozen=True)
class Goal:
    """A goal definition from ``goals.csv``."""

    goal_id: str
    area: str
    title: str
    horizon: str | None
    target_date: date | None
    metric_name: str | None
    metric_target: float | None
    metric_current: float | None
    status: str
    last_updated: date | None
    notes: str | None


@dataclass(frozen=True)
class GoalStats:
    """Computed analytics for a single goal as of a given date."""

    goal: Goal
    progress_percent: float | None
    progress_ratio: float | None
    days_until_target: int | None
    expected_progress_percent: float | None
    on_track: bool | None
    days_since_update: int | None
    status_label: str


def _parse_float(raw: str) -> float | None:
    raw = raw.strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_date(raw: str) -> date | None:
    raw = raw.strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _normalize_horizon(raw: str) -> str | None:
    value = raw.strip().lower()
    return value if value in HORIZON_DAYS else None


def load_goals(path: Path = GOALS_CSV) -> list[Goal]:
    """Load goal definitions. Silently skips rows missing a goal_id."""
    goals: list[Goal] = []
    if not path.exists():
        return goals
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            goal_id = (row.get("goal_id") or "").strip()
            if not goal_id:
                continue
            goals.append(
                Goal(
                    goal_id=goal_id,
                    area=(row.get("area") or "").strip(),
                    title=(row.get("title") or goal_id).strip(),
                    horizon=_normalize_horizon(row.get("horizon", "")),
                    target_date=_parse_date(row.get("target_date", "")),
                    metric_name=(row.get("metric_name") or "").strip() or None,
                    metric_target=_parse_float(row.get("metric_target", "")),
                    metric_current=_parse_float(row.get("metric_current", "")),
                    status=(row.get("status") or "active").strip().lower(),
                    last_updated=_parse_date(row.get("last_updated", "")),
                    notes=(row.get("notes") or "").strip() or None,
                )
            )
    return goals


def _progress(
    current: float | None, target: float | None
) -> tuple[float | None, float | None]:
    """Return (percent_capped_0_100, raw_ratio).

    A target of zero is treated as "no measurable progress" — the ratio is
    undefined, so both values are ``None``.
    """
    if current is None or target is None or target == 0:
        return None, None
    ratio = current / target
    percent = max(0.0, min(100.0, ratio * 100.0))
    return percent, ratio


def _expected_progress(goal: Goal, today: date) -> float | None:
    """Linear expected progress for a horizon-anchored goal.

    Derives a notional start date as ``target_date - horizon_days[horizon]``.
    Returns the percent of the window that has elapsed, clamped to 0-100.
    Returns ``None`` when the horizon or target_date is missing.
    """
    if goal.target_date is None or goal.horizon is None:
        return None
    span = HORIZON_DAYS[goal.horizon]
    start = goal.target_date - timedelta(days=span)
    elapsed = (today - start).days
    return max(0.0, min(100.0, elapsed / span * 100.0))


def _status_label(
    goal: Goal, days_until_target: int | None, ratio: float | None
) -> str:
    """Pick a human-readable status string.

    - terminal statuses (completed/paused/dropped) pass through unchanged
    - an active goal whose metric has hit/exceeded target is ``achieved``
    - an active goal past its target_date is ``overdue``
    - otherwise ``active``
    """
    if goal.status in {"completed", "paused", "dropped"}:
        return goal.status
    if ratio is not None and ratio >= 1.0:
        return "achieved"
    if days_until_target is not None and days_until_target < 0:
        return "overdue"
    return "active"


def compute_stats(goal: Goal, today: date) -> GoalStats:
    """Compute all stats for a single goal."""
    percent, ratio = _progress(goal.metric_current, goal.metric_target)
    days_until_target = (
        (goal.target_date - today).days if goal.target_date is not None else None
    )
    expected = _expected_progress(goal, today)
    if percent is None or expected is None:
        on_track = None
    else:
        on_track = percent + 1e-9 >= expected
    days_since_update = (
        (today - goal.last_updated).days if goal.last_updated is not None else None
    )
    return GoalStats(
        goal=goal,
        progress_percent=percent,
        progress_ratio=ratio,
        days_until_target=days_until_target,
        expected_progress_percent=expected,
        on_track=on_track,
        days_since_update=days_since_update,
        status_label=_status_label(goal, days_until_target, ratio),
    )


def analyze(
    goals_path: Path = GOALS_CSV,
    today: date | None = None,
    include_inactive: bool = False,
) -> list[GoalStats]:
    """Load goals and compute stats for each.

    Sorted active-first, then ascending days-until-target (overdue first,
    far-future last; goals without a target_date sort to the end), then
    title — surfacing the most-pressing goals at the top of reports.
    """
    goals = load_goals(goals_path)
    anchor = today or date.today()
    selected = [
        g for g in goals if include_inactive or g.status not in {"completed", "dropped"}
    ]
    stats = [compute_stats(g, anchor) for g in selected]

    def _sort_key(s: GoalStats) -> tuple[int, int, int, str]:
        active_first = 0 if s.goal.status == "active" else 1
        # None days_until_target sorts after numeric values
        no_target = 1 if s.days_until_target is None else 0
        days = s.days_until_target if s.days_until_target is not None else 0
        return (active_first, no_target, days, s.goal.title.lower())

    stats.sort(key=_sort_key)
    return stats


def _fmt_percent(value: float | None) -> str:
    return f"{value:5.1f}%" if value is not None else "    -"


def _fmt_days(value: int | None) -> str:
    if value is None:
        return "    -"
    return f"{value:+5d}d"


def _fmt_on_track(value: bool | None) -> str:
    if value is None:
        return " - "
    return "yes" if value else "no "


def format_report(stats: list[GoalStats]) -> str:
    """Render a compact, human-readable table of goal stats."""
    if not stats:
        return "No goals found.\n"

    header = (
        f"{'Goal':<30} {'Area':<10} {'Status':<10} "
        f"{'Progress':>9} {'Expected':>9} {'On track':>9} "
        f"{'Days left':>10} {'Stale':>6}"
    )
    sep = "-" * len(header)
    lines = [header, sep]
    for s in stats:
        title = s.goal.title[:30]
        area = s.goal.area[:10]
        stale = f"{s.days_since_update}d" if s.days_since_update is not None else "-"
        lines.append(
            f"{title:<30} {area:<10} {s.status_label:<10} "
            f"{_fmt_percent(s.progress_percent):>9} "
            f"{_fmt_percent(s.expected_progress_percent):>9} "
            f"{_fmt_on_track(s.on_track):>9} "
            f"{_fmt_days(s.days_until_target):>10} {stale:>6}"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Print a formatted goal analytics report."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--goals",
        type=Path,
        default=GOALS_CSV,
        help="Path to goals.csv (default: canonical location).",
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
        help="Include goals with status 'completed' or 'dropped' in the report.",
    )
    args = parser.parse_args(argv)

    stats = analyze(
        goals_path=args.goals,
        today=args.today,
        include_inactive=args.include_inactive,
    )
    sys.stdout.write(format_report(stats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
