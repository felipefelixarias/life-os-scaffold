#!/usr/bin/env python3
"""Task aging, overdue, and portfolio analytics.

Reads ``tasks.csv`` and produces per-task statistics (days until due,
staleness, overdue flag, status label) plus portfolio-level rollups
(counts by status / priority / domain, velocity, WIP). Run as a script
to print a summary table; import the helpers to feed ``/status``,
``/daily``, ``/triage``, and ``/weekly-review``.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TASKS_CSV = REPO_ROOT / "01-ops" / "life-os" / "data" / "canonical" / "tasks.csv"

TERMINAL_STATUSES: frozenset[str] = frozenset({"completed", "done", "dropped"})
DEFAULT_STALE_DAYS = 14
PRIORITY_ORDER: dict[str, int] = {"P1": 0, "P2": 1, "P3": 2}


@dataclass(frozen=True)
class Task:
    """A task definition from ``tasks.csv``."""

    task_id: str
    project_id: str | None
    title: str
    domain: str | None
    status: str
    priority: str | None
    effort_mins: int | None
    due_date: date | None
    energy: str | None
    scheduled_date: date | None
    last_updated: date | None


@dataclass(frozen=True)
class TaskStats:
    """Computed analytics for a single task as of a given date."""

    task: Task
    days_until_due: int | None
    days_since_update: int | None
    is_overdue: bool
    is_stale: bool
    is_scheduled: bool
    status_label: str


@dataclass(frozen=True)
class TaskPortfolio:
    """Portfolio-level rollups across a collection of tasks."""

    total: int
    by_status: dict[str, int] = field(default_factory=dict)
    by_priority: dict[str, int] = field(default_factory=dict)
    by_domain: dict[str, int] = field(default_factory=dict)
    active_count: int = 0
    wip_count: int = 0
    blocked_count: int = 0
    overdue_count: int = 0
    stale_count: int = 0
    scheduled_count: int = 0
    completed_last_7_days: int = 0
    completed_last_30_days: int = 0


def _parse_int(raw: str) -> int | None:
    raw = raw.strip()
    if not raw:
        return None
    try:
        return int(raw)
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


def _normalize_priority(raw: str) -> str | None:
    value = raw.strip().upper()
    return value if value in PRIORITY_ORDER else None


def _normalize_energy(raw: str) -> str | None:
    value = raw.strip().lower()
    return value if value in {"low", "medium", "high"} else None


def load_tasks(path: Path = TASKS_CSV) -> list[Task]:
    """Load task definitions. Silently skips rows missing a task_id."""
    tasks: list[Task] = []
    if not path.exists():
        return tasks
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            task_id = (row.get("task_id") or "").strip()
            if not task_id:
                continue
            tasks.append(
                Task(
                    task_id=task_id,
                    project_id=(row.get("project_id") or "").strip() or None,
                    title=(row.get("title") or task_id).strip(),
                    domain=(row.get("domain") or "").strip() or None,
                    status=(row.get("status") or "queued").strip().lower(),
                    priority=_normalize_priority(row.get("priority", "")),
                    effort_mins=_parse_int(row.get("effort_mins", "")),
                    due_date=_parse_date(row.get("due_date", "")),
                    energy=_normalize_energy(row.get("energy", "")),
                    scheduled_date=_parse_date(row.get("scheduled_date", "")),
                    last_updated=_parse_date(row.get("last_updated", "")),
                )
            )
    return tasks


def _status_label(task: Task, is_overdue: bool, is_stale: bool) -> str:
    """Pick a human-readable status string.

    Terminal statuses pass through. For non-terminal tasks, the most
    actionable signal wins: ``overdue`` > ``blocked`` > ``stale`` > the raw
    status (``in_progress`` / ``queued``).
    """
    if task.status in TERMINAL_STATUSES:
        return task.status
    if is_overdue:
        return "overdue"
    if task.status == "blocked":
        return "blocked"
    if is_stale:
        return "stale"
    return task.status


def compute_stats(
    task: Task,
    today: date,
    stale_threshold_days: int = DEFAULT_STALE_DAYS,
) -> TaskStats:
    """Compute all stats for a single task."""
    days_until_due = (task.due_date - today).days if task.due_date is not None else None
    days_since_update = (
        (today - task.last_updated).days if task.last_updated is not None else None
    )
    is_terminal = task.status in TERMINAL_STATUSES
    is_overdue = not is_terminal and days_until_due is not None and days_until_due < 0
    is_stale = (
        not is_terminal
        and days_since_update is not None
        and days_since_update >= stale_threshold_days
    )
    is_scheduled = task.scheduled_date is not None
    return TaskStats(
        task=task,
        days_until_due=days_until_due,
        days_since_update=days_since_update,
        is_overdue=is_overdue,
        is_stale=is_stale,
        is_scheduled=is_scheduled,
        status_label=_status_label(task, is_overdue, is_stale),
    )


def summarize(stats: list[TaskStats], today: date | None = None) -> TaskPortfolio:
    """Build a ``TaskPortfolio`` rollup from a list of per-task stats.

    ``completed_last_7_days`` / ``completed_last_30_days`` count terminal
    tasks (status ``completed``/``done``) whose ``last_updated`` falls in
    the respective window ending at ``today`` (defaults to today()).
    """
    anchor = today or date.today()
    by_status: Counter[str] = Counter()
    by_priority: Counter[str] = Counter()
    by_domain: Counter[str] = Counter()
    active = wip = blocked = overdue = stale = scheduled = 0
    done_7 = done_30 = 0

    for s in stats:
        t = s.task
        by_status[t.status] += 1
        by_priority[t.priority or "unset"] += 1
        by_domain[t.domain or "unset"] += 1

        if t.status not in TERMINAL_STATUSES:
            active += 1
            if t.status == "in_progress":
                wip += 1
            if t.status == "blocked":
                blocked += 1
        if s.is_overdue:
            overdue += 1
        if s.is_stale:
            stale += 1
        if s.is_scheduled and t.status not in TERMINAL_STATUSES:
            scheduled += 1

        if t.status in {"completed", "done"} and t.last_updated is not None:
            delta = (anchor - t.last_updated).days
            if 0 <= delta < 7:
                done_7 += 1
            if 0 <= delta < 30:
                done_30 += 1

    return TaskPortfolio(
        total=len(stats),
        by_status=dict(by_status),
        by_priority=dict(by_priority),
        by_domain=dict(by_domain),
        active_count=active,
        wip_count=wip,
        blocked_count=blocked,
        overdue_count=overdue,
        stale_count=stale,
        scheduled_count=scheduled,
        completed_last_7_days=done_7,
        completed_last_30_days=done_30,
    )


def analyze(
    tasks_path: Path = TASKS_CSV,
    today: date | None = None,
    include_terminal: bool = False,
    stale_threshold_days: int = DEFAULT_STALE_DAYS,
) -> list[TaskStats]:
    """Load tasks and compute stats for each.

    Sorted non-terminal-first, then ascending days-until-due (overdue
    first, far-future last; tasks without a due_date sort to the end),
    then by priority (P1 < P2 < P3 < unset), then title — surfacing the
    most-pressing tasks at the top of reports.
    """
    tasks = load_tasks(tasks_path)
    anchor = today or date.today()
    selected = [
        t for t in tasks if include_terminal or t.status not in TERMINAL_STATUSES
    ]
    stats = [compute_stats(t, anchor, stale_threshold_days) for t in selected]

    def _sort_key(s: TaskStats) -> tuple[int, int, int, int, str]:
        terminal_last = 1 if s.task.status in TERMINAL_STATUSES else 0
        no_due = 1 if s.days_until_due is None else 0
        days = s.days_until_due if s.days_until_due is not None else 0
        prio = PRIORITY_ORDER.get(s.task.priority or "", 99)
        return (terminal_last, no_due, days, prio, s.task.title.lower())

    stats.sort(key=_sort_key)
    return stats


def _fmt_days(value: int | None) -> str:
    if value is None:
        return "    -"
    return f"{value:+5d}d"


def _fmt_stale(value: int | None) -> str:
    return f"{value}d" if value is not None else "-"


def format_report(
    stats: list[TaskStats], portfolio: TaskPortfolio | None = None
) -> str:
    """Render a compact, human-readable table of task stats."""
    if not stats:
        return "No tasks found.\n"

    header = (
        f"{'Task':<34} {'Domain':<12} {'Prio':<4} "
        f"{'Status':<11} {'Due':>10} {'Stale':>6}"
    )
    sep = "-" * len(header)
    lines = [header, sep]
    for s in stats:
        title = s.task.title[:34]
        domain = (s.task.domain or "-")[:12]
        prio = s.task.priority or "-"
        lines.append(
            f"{title:<34} {domain:<12} {prio:<4} "
            f"{s.status_label:<11} {_fmt_days(s.days_until_due):>10} "
            f"{_fmt_stale(s.days_since_update):>6}"
        )
    if portfolio is not None:
        lines.append("")
        lines.append(
            f"Portfolio: {portfolio.total} total, "
            f"{portfolio.active_count} active "
            f"(WIP {portfolio.wip_count}, blocked {portfolio.blocked_count}), "
            f"{portfolio.overdue_count} overdue, "
            f"{portfolio.stale_count} stale, "
            f"{portfolio.scheduled_count} scheduled. "
            f"Completed: {portfolio.completed_last_7_days} in 7d, "
            f"{portfolio.completed_last_30_days} in 30d."
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Print a formatted task analytics report."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--tasks",
        type=Path,
        default=TASKS_CSV,
        help="Path to tasks.csv (default: canonical location).",
    )
    parser.add_argument(
        "--today",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=None,
        help="Override 'today' as YYYY-MM-DD (useful for deterministic reports).",
    )
    parser.add_argument(
        "--include-terminal",
        action="store_true",
        help="Include tasks with status 'completed', 'done', or 'dropped'.",
    )
    parser.add_argument(
        "--stale-days",
        type=int,
        default=DEFAULT_STALE_DAYS,
        help=f"Staleness threshold in days (default: {DEFAULT_STALE_DAYS}).",
    )
    args = parser.parse_args(argv)

    stats = analyze(
        tasks_path=args.tasks,
        today=args.today,
        include_terminal=args.include_terminal,
        stale_threshold_days=args.stale_days,
    )
    portfolio = summarize(stats, today=args.today)
    sys.stdout.write(format_report(stats, portfolio))
    return 0


if __name__ == "__main__":
    sys.exit(main())
