#!/usr/bin/env python3
"""Project portfolio analytics — status, staleness, overdue, and area rollups.

Reads ``projects.csv`` and produces per-project statistics (days until target,
staleness, timeline elapsed percent, overdue/stale flags) plus a portfolio
rollup (counts by status and area, completed-recent counts). Run as a script
for a summary table; import the helpers to feed ``/status``, ``/daily``,
``/weekly-review``, and the project-tracking commands.
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
PROJECTS_CSV = REPO_ROOT / "01-ops" / "life-os" / "data" / "canonical" / "projects.csv"

DEFAULT_STALE_THRESHOLD_DAYS = 30
TERMINAL_STATUSES = frozenset({"completed"})
RECENT_COMPLETION_WINDOW_DAYS = 30


@dataclass(frozen=True)
class Project:
    """A project definition from ``projects.csv``."""

    project_id: str
    area: str
    name: str
    status: str
    start_date: date | None
    target_date: date | None
    description: str | None
    last_updated: date | None
    notes: str | None
    active: bool | None


@dataclass(frozen=True)
class ProjectStats:
    """Computed analytics for a single project as of a given date."""

    project: Project
    days_until_target: int | None
    days_since_start: int | None
    days_since_update: int | None
    duration_days: int | None
    elapsed_percent: float | None
    is_overdue: bool
    is_stale: bool
    is_active: bool
    status_label: str


@dataclass(frozen=True)
class ProjectPortfolio:
    """Aggregate counts across a collection of project stats."""

    total: int
    status_counts: dict[str, int] = field(default_factory=dict)
    area_counts: dict[str, int] = field(default_factory=dict)
    active_count: int = 0
    planning_count: int = 0
    paused_count: int = 0
    completed_count: int = 0
    overdue_count: int = 0
    stale_count: int = 0
    no_target_count: int = 0
    completed_last_30_days: int = 0


def _parse_date(raw: str) -> date | None:
    raw = raw.strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_bool(raw: str) -> bool | None:
    value = raw.strip().lower()
    if not value:
        return None
    if value in {"true", "1", "yes", "y"}:
        return True
    if value in {"false", "0", "no", "n"}:
        return False
    return None


def _normalize_status(raw: str) -> str:
    value = raw.strip().lower()
    return value or "planning"


def load_projects(path: Path = PROJECTS_CSV) -> list[Project]:
    """Load project definitions. Silently skips rows missing a project_id."""
    projects: list[Project] = []
    if not path.exists():
        return projects
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            project_id = (row.get("project_id") or "").strip()
            if not project_id:
                continue
            projects.append(
                Project(
                    project_id=project_id,
                    area=(row.get("area") or "").strip(),
                    name=(row.get("name") or project_id).strip(),
                    status=_normalize_status(row.get("status", "")),
                    start_date=_parse_date(row.get("start_date", "")),
                    target_date=_parse_date(row.get("target_date", "")),
                    description=(row.get("description") or "").strip() or None,
                    last_updated=_parse_date(row.get("last_updated", "")),
                    notes=(row.get("notes") or "").strip() or None,
                    active=_parse_bool(row.get("active", "")),
                )
            )
    return projects


def _elapsed_percent(
    start: date | None, target: date | None, today: date
) -> tuple[int | None, float | None]:
    """Return (duration_days, elapsed_percent clamped 0-100).

    ``duration_days`` is the span from start to target. ``elapsed_percent``
    shows how far the project has moved through that window. Both are
    ``None`` when either endpoint is missing or the window is non-positive.
    """
    if start is None or target is None:
        return None, None
    duration = (target - start).days
    if duration <= 0:
        return None, None
    elapsed_days = (today - start).days
    ratio = elapsed_days / duration
    percent = max(0.0, min(100.0, ratio * 100.0))
    return duration, percent


def _status_label(
    project: Project,
    days_until_target: int | None,
    is_stale: bool,
) -> str:
    """Pick a human-readable status string.

    - terminal statuses (``completed``) pass through unchanged
    - non-terminal resolves in priority order: overdue > stale > raw status
    """
    if project.status in TERMINAL_STATUSES:
        return project.status
    if days_until_target is not None and days_until_target < 0:
        return "overdue"
    if is_stale:
        return "stale"
    return project.status


def compute_stats(
    project: Project,
    today: date,
    stale_threshold_days: int = DEFAULT_STALE_THRESHOLD_DAYS,
) -> ProjectStats:
    """Compute all stats for a single project."""
    days_until_target = (
        (project.target_date - today).days if project.target_date is not None else None
    )
    days_since_start = (
        (today - project.start_date).days if project.start_date is not None else None
    )
    days_since_update = (
        (today - project.last_updated).days
        if project.last_updated is not None
        else None
    )
    duration_days, elapsed_percent = _elapsed_percent(
        project.start_date, project.target_date, today
    )

    is_terminal = project.status in TERMINAL_STATUSES
    is_overdue = (
        not is_terminal and days_until_target is not None and days_until_target < 0
    )
    is_stale = (
        not is_terminal
        and days_since_update is not None
        and days_since_update >= stale_threshold_days
    )
    # A project is "active" for dashboard purposes when its status is active
    # AND the optional ``active`` boolean column is not explicitly False.
    is_active = project.status == "active" and project.active is not False

    return ProjectStats(
        project=project,
        days_until_target=days_until_target,
        days_since_start=days_since_start,
        days_since_update=days_since_update,
        duration_days=duration_days,
        elapsed_percent=elapsed_percent,
        is_overdue=is_overdue,
        is_stale=is_stale,
        is_active=is_active,
        status_label=_status_label(project, days_until_target, is_stale),
    )


def summarize(stats: list[ProjectStats], today: date) -> ProjectPortfolio:
    """Roll stats up into a portfolio-level summary."""
    status_counts: Counter[str] = Counter()
    area_counts: Counter[str] = Counter()
    active_count = 0
    planning_count = 0
    paused_count = 0
    completed_count = 0
    overdue_count = 0
    stale_count = 0
    no_target_count = 0
    completed_recent = 0

    for s in stats:
        status_counts[s.project.status] += 1
        if s.project.area:
            area_counts[s.project.area] += 1
        if s.project.status == "active":
            active_count += 1
        elif s.project.status == "planning":
            planning_count += 1
        elif s.project.status == "paused":
            paused_count += 1
        elif s.project.status == "completed":
            completed_count += 1
        if s.is_overdue:
            overdue_count += 1
        if s.is_stale:
            stale_count += 1
        if s.project.target_date is None and s.project.status not in TERMINAL_STATUSES:
            no_target_count += 1
        if (
            s.project.status == "completed"
            and s.project.last_updated is not None
            and 0
            <= (today - s.project.last_updated).days
            < RECENT_COMPLETION_WINDOW_DAYS
        ):
            completed_recent += 1

    return ProjectPortfolio(
        total=len(stats),
        status_counts=dict(status_counts),
        area_counts=dict(area_counts),
        active_count=active_count,
        planning_count=planning_count,
        paused_count=paused_count,
        completed_count=completed_count,
        overdue_count=overdue_count,
        stale_count=stale_count,
        no_target_count=no_target_count,
        completed_last_30_days=completed_recent,
    )


def analyze(
    projects_path: Path = PROJECTS_CSV,
    today: date | None = None,
    include_completed: bool = False,
    stale_threshold_days: int = DEFAULT_STALE_THRESHOLD_DAYS,
) -> list[ProjectStats]:
    """Load projects and compute stats for each.

    Sorted non-terminal-first, then ascending days-until-target (overdue
    first, far-future last; projects without a target_date sort to the end),
    then name — surfacing the most-pressing projects at the top of reports.
    """
    projects = load_projects(projects_path)
    anchor = today or date.today()
    selected = [
        p for p in projects if include_completed or p.status not in TERMINAL_STATUSES
    ]
    stats = [compute_stats(p, anchor, stale_threshold_days) for p in selected]

    def _sort_key(s: ProjectStats) -> tuple[int, int, int, str]:
        terminal_last = 1 if s.project.status in TERMINAL_STATUSES else 0
        # None days_until_target sorts after numeric values
        no_target = 1 if s.days_until_target is None else 0
        days = s.days_until_target if s.days_until_target is not None else 0
        return (terminal_last, no_target, days, s.project.name.lower())

    stats.sort(key=_sort_key)
    return stats


def _fmt_days(value: int | None) -> str:
    if value is None:
        return "    -"
    return f"{value:+5d}d"


def _fmt_percent(value: float | None) -> str:
    return f"{value:5.1f}%" if value is not None else "    -"


def format_report(stats: list[ProjectStats], portfolio: ProjectPortfolio) -> str:
    """Render a compact, human-readable project analytics report."""
    if not stats:
        return "No projects found.\n"

    header = (
        f"{'Project':<30} {'Area':<12} {'Status':<10} "
        f"{'Elapsed':>8} {'Days left':>10} {'Stale':>7}"
    )
    sep = "-" * len(header)
    lines = [header, sep]
    for s in stats:
        name = s.project.name[:30]
        area = s.project.area[:12]
        stale = f"{s.days_since_update}d" if s.days_since_update is not None else "-"
        lines.append(
            f"{name:<30} {area:<12} {s.status_label:<10} "
            f"{_fmt_percent(s.elapsed_percent):>8} "
            f"{_fmt_days(s.days_until_target):>10} {stale:>7}"
        )

    lines.append("")
    lines.append(
        f"Total: {portfolio.total}  "
        f"active: {portfolio.active_count}  "
        f"planning: {portfolio.planning_count}  "
        f"paused: {portfolio.paused_count}  "
        f"completed: {portfolio.completed_count}"
    )
    lines.append(
        f"Overdue: {portfolio.overdue_count}  "
        f"stale: {portfolio.stale_count}  "
        f"no target: {portfolio.no_target_count}  "
        f"completed 30d: {portfolio.completed_last_30_days}"
    )
    if portfolio.area_counts:
        by_area = ", ".join(
            f"{area}={count}"
            for area, count in sorted(
                portfolio.area_counts.items(), key=lambda kv: (-kv[1], kv[0])
            )
        )
        lines.append(f"By area: {by_area}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Print a formatted project analytics report."""
    doc = __doc__ or ""
    parser = argparse.ArgumentParser(description=doc.splitlines()[0])
    parser.add_argument(
        "--projects",
        type=Path,
        default=PROJECTS_CSV,
        help="Path to projects.csv (default: canonical location).",
    )
    parser.add_argument(
        "--today",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=None,
        help="Override 'today' as YYYY-MM-DD (useful for deterministic reports).",
    )
    parser.add_argument(
        "--include-completed",
        action="store_true",
        help="Include projects with status 'completed' in the report.",
    )
    parser.add_argument(
        "--stale-days",
        type=int,
        default=DEFAULT_STALE_THRESHOLD_DAYS,
        help=(
            "Days since last_updated before a non-terminal project is flagged "
            f"as stale (default: {DEFAULT_STALE_THRESHOLD_DAYS})."
        ),
    )
    args = parser.parse_args(argv)

    anchor = args.today or date.today()
    stats = analyze(
        projects_path=args.projects,
        today=anchor,
        include_completed=args.include_completed,
        stale_threshold_days=args.stale_days,
    )
    portfolio = summarize(stats, anchor)
    sys.stdout.write(format_report(stats, portfolio))
    return 0


if __name__ == "__main__":
    sys.exit(main())
