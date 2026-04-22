#!/usr/bin/env python3
"""Tests for project_analytics.py."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "01-ops" / "life-os" / "scripts"),
)

import project_analytics as pa

PROJECTS_HEADER = (
    "project_id,area,name,status,start_date,target_date,"
    "description,last_updated,notes,active\n"
)


def _write_projects(path: Path, rows: list[str]) -> Path:
    path.write_text(PROJECTS_HEADER + "\n".join(rows) + ("\n" if rows else ""))
    return path


# ---------------------------------------------------------------------------
# Parser helpers
# ---------------------------------------------------------------------------


def test_parse_date_blank_returns_none() -> None:
    assert pa._parse_date("") is None
    assert pa._parse_date("   ") is None


def test_parse_date_invalid_returns_none() -> None:
    assert pa._parse_date("not-a-date") is None
    assert pa._parse_date("2026-13-40") is None


def test_parse_date_valid() -> None:
    assert pa._parse_date("2026-04-22") == date(2026, 4, 22)


def test_parse_bool_truthy_values() -> None:
    for raw in ("true", "True", " TRUE ", "1", "yes", "Y"):
        assert pa._parse_bool(raw) is True


def test_parse_bool_falsy_values() -> None:
    for raw in ("false", "False", " FALSE ", "0", "no", "N"):
        assert pa._parse_bool(raw) is False


def test_parse_bool_blank_returns_none() -> None:
    assert pa._parse_bool("") is None
    assert pa._parse_bool("   ") is None


def test_parse_bool_unknown_returns_none() -> None:
    assert pa._parse_bool("maybe") is None


def test_normalize_status_blank_defaults_to_planning() -> None:
    assert pa._normalize_status("") == "planning"
    assert pa._normalize_status("   ") == "planning"


def test_normalize_status_lowercases_and_strips() -> None:
    assert pa._normalize_status(" Active ") == "active"
    assert pa._normalize_status("COMPLETED") == "completed"


# ---------------------------------------------------------------------------
# load_projects
# ---------------------------------------------------------------------------


def test_load_projects_missing_file_returns_empty(tmp_path: Path) -> None:
    assert pa.load_projects(tmp_path / "nope.csv") == []


def test_load_projects_empty_file_returns_empty(tmp_path: Path) -> None:
    path = _write_projects(tmp_path / "projects.csv", [])
    assert pa.load_projects(path) == []


def test_load_projects_skips_rows_without_project_id(tmp_path: Path) -> None:
    path = _write_projects(
        tmp_path / "projects.csv",
        [
            ",health,No ID,active,,,,,,",
            "p1,health,Has ID,active,,,,,,",
        ],
    )
    projects = pa.load_projects(path)
    assert len(projects) == 1
    assert projects[0].project_id == "p1"


def test_load_projects_falls_back_to_project_id_for_name(tmp_path: Path) -> None:
    path = _write_projects(
        tmp_path / "projects.csv",
        ["p1,health,,active,,,,,,"],
    )
    projects = pa.load_projects(path)
    assert projects[0].name == "p1"


def test_load_projects_parses_all_fields(tmp_path: Path) -> None:
    path = _write_projects(
        tmp_path / "projects.csv",
        [
            "p1,career,Build resume,active,2026-01-01,2026-06-30,"
            "A project,2026-04-01,Some notes,true",
        ],
    )
    [project] = pa.load_projects(path)
    assert project.project_id == "p1"
    assert project.area == "career"
    assert project.name == "Build resume"
    assert project.status == "active"
    assert project.start_date == date(2026, 1, 1)
    assert project.target_date == date(2026, 6, 30)
    assert project.description == "A project"
    assert project.last_updated == date(2026, 4, 1)
    assert project.notes == "Some notes"
    assert project.active is True


def test_load_projects_blank_status_defaults_to_planning(tmp_path: Path) -> None:
    path = _write_projects(
        tmp_path / "projects.csv",
        ["p1,health,Blank,,,,,,,"],
    )
    [project] = pa.load_projects(path)
    assert project.status == "planning"


def test_load_projects_blank_description_and_notes_become_none(
    tmp_path: Path,
) -> None:
    path = _write_projects(
        tmp_path / "projects.csv",
        ["p1,health,Blank,active,,,,,,"],
    )
    [project] = pa.load_projects(path)
    assert project.description is None
    assert project.notes is None


# ---------------------------------------------------------------------------
# _elapsed_percent
# ---------------------------------------------------------------------------


def test_elapsed_percent_missing_endpoints_returns_none() -> None:
    assert pa._elapsed_percent(None, date(2026, 6, 1), date(2026, 4, 1)) == (None, None)
    assert pa._elapsed_percent(date(2026, 1, 1), None, date(2026, 4, 1)) == (None, None)


def test_elapsed_percent_zero_duration_returns_none() -> None:
    same = date(2026, 4, 1)
    assert pa._elapsed_percent(same, same, same) == (None, None)


def test_elapsed_percent_inverted_window_returns_none() -> None:
    # target_date before start_date → treat as unknown, not negative duration
    assert pa._elapsed_percent(
        date(2026, 6, 1), date(2026, 1, 1), date(2026, 4, 1)
    ) == (None, None)


def test_elapsed_percent_midway_through_window() -> None:
    duration, percent = pa._elapsed_percent(
        date(2026, 1, 1), date(2026, 7, 1), date(2026, 4, 1)
    )
    assert duration == 181
    assert percent is not None
    assert 49.0 < percent < 51.0


def test_elapsed_percent_clamps_below_start() -> None:
    duration, percent = pa._elapsed_percent(
        date(2026, 6, 1), date(2026, 12, 1), date(2026, 4, 1)
    )
    assert duration == 183
    assert percent == 0.0


def test_elapsed_percent_clamps_past_target() -> None:
    duration, percent = pa._elapsed_percent(
        date(2026, 1, 1), date(2026, 3, 1), date(2026, 6, 1)
    )
    assert duration == 59
    assert percent == 100.0


# ---------------------------------------------------------------------------
# compute_stats
# ---------------------------------------------------------------------------


def _project(**overrides: object) -> pa.Project:
    defaults: dict[str, object] = {
        "project_id": "p1",
        "area": "health",
        "name": "Project 1",
        "status": "active",
        "start_date": None,
        "target_date": None,
        "description": None,
        "last_updated": None,
        "notes": None,
        "active": None,
    }
    defaults.update(overrides)
    return pa.Project(**defaults)  # type: ignore[arg-type]


def test_compute_stats_minimal_project_has_no_dates() -> None:
    stats = pa.compute_stats(_project(), date(2026, 4, 22))
    assert stats.days_until_target is None
    assert stats.days_since_start is None
    assert stats.days_since_update is None
    assert stats.duration_days is None
    assert stats.elapsed_percent is None
    assert stats.is_overdue is False
    assert stats.is_stale is False
    assert stats.is_active is True  # active status, active column unset
    assert stats.status_label == "active"


def test_compute_stats_overdue_project_is_flagged() -> None:
    stats = pa.compute_stats(
        _project(target_date=date(2026, 3, 1)),
        date(2026, 4, 22),
    )
    assert stats.days_until_target == -52
    assert stats.is_overdue is True
    assert stats.status_label == "overdue"


def test_compute_stats_future_target_is_not_overdue() -> None:
    stats = pa.compute_stats(
        _project(target_date=date(2026, 6, 1)),
        date(2026, 4, 22),
    )
    assert stats.days_until_target == 40
    assert stats.is_overdue is False
    assert stats.status_label == "active"


def test_compute_stats_target_today_is_not_overdue() -> None:
    stats = pa.compute_stats(
        _project(target_date=date(2026, 4, 22)),
        date(2026, 4, 22),
    )
    assert stats.days_until_target == 0
    assert stats.is_overdue is False


def test_compute_stats_stale_when_update_past_threshold() -> None:
    stats = pa.compute_stats(
        _project(last_updated=date(2026, 3, 1)),
        date(2026, 4, 22),
        stale_threshold_days=30,
    )
    assert stats.days_since_update == 52
    assert stats.is_stale is True
    assert stats.status_label == "stale"


def test_compute_stats_stale_threshold_boundary_inclusive() -> None:
    stats = pa.compute_stats(
        _project(last_updated=date(2026, 3, 23)),
        date(2026, 4, 22),
        stale_threshold_days=30,
    )
    assert stats.days_since_update == 30
    assert stats.is_stale is True


def test_compute_stats_status_label_prefers_overdue_over_stale() -> None:
    stats = pa.compute_stats(
        _project(
            target_date=date(2026, 3, 1),
            last_updated=date(2026, 3, 1),
        ),
        date(2026, 4, 22),
    )
    assert stats.is_overdue is True
    assert stats.is_stale is True
    assert stats.status_label == "overdue"


def test_compute_stats_completed_project_is_not_overdue_even_when_past() -> None:
    stats = pa.compute_stats(
        _project(
            status="completed",
            target_date=date(2026, 1, 1),
            last_updated=date(2026, 1, 10),
        ),
        date(2026, 4, 22),
    )
    assert stats.is_overdue is False
    assert stats.is_stale is False
    assert stats.status_label == "completed"


def test_compute_stats_is_active_requires_active_status() -> None:
    assert (
        pa.compute_stats(_project(status="planning"), date(2026, 4, 22)).is_active
        is False
    )
    assert (
        pa.compute_stats(_project(status="paused"), date(2026, 4, 22)).is_active
        is False
    )
    assert (
        pa.compute_stats(_project(status="active"), date(2026, 4, 22)).is_active is True
    )


def test_compute_stats_is_active_respects_active_false_flag() -> None:
    stats = pa.compute_stats(_project(status="active", active=False), date(2026, 4, 22))
    assert stats.is_active is False


def test_compute_stats_is_active_ignores_active_true_flag_on_non_active_status() -> (
    None
):
    stats = pa.compute_stats(_project(status="paused", active=True), date(2026, 4, 22))
    assert stats.is_active is False


def test_compute_stats_computes_duration_and_elapsed() -> None:
    stats = pa.compute_stats(
        _project(
            start_date=date(2026, 1, 1),
            target_date=date(2026, 7, 1),
        ),
        date(2026, 4, 1),
    )
    assert stats.duration_days == 181
    assert stats.elapsed_percent is not None
    assert 49.0 < stats.elapsed_percent < 51.0
    assert stats.days_since_start == 90


# ---------------------------------------------------------------------------
# summarize
# ---------------------------------------------------------------------------


def test_summarize_empty_stats_is_zero() -> None:
    portfolio = pa.summarize([], date(2026, 4, 22))
    assert portfolio.total == 0
    assert portfolio.active_count == 0
    assert portfolio.status_counts == {}
    assert portfolio.area_counts == {}


def test_summarize_counts_by_status() -> None:
    today = date(2026, 4, 22)
    projects = [
        _project(project_id="p1", status="active"),
        _project(project_id="p2", status="active"),
        _project(project_id="p3", status="planning"),
        _project(project_id="p4", status="paused"),
        _project(project_id="p5", status="completed"),
    ]
    stats = [pa.compute_stats(p, today) for p in projects]
    portfolio = pa.summarize(stats, today)

    assert portfolio.total == 5
    assert portfolio.active_count == 2
    assert portfolio.planning_count == 1
    assert portfolio.paused_count == 1
    assert portfolio.completed_count == 1
    assert portfolio.status_counts == {
        "active": 2,
        "planning": 1,
        "paused": 1,
        "completed": 1,
    }


def test_summarize_counts_by_area_ignores_blank_areas() -> None:
    today = date(2026, 4, 22)
    projects = [
        _project(project_id="p1", area="health"),
        _project(project_id="p2", area="health"),
        _project(project_id="p3", area="career"),
        _project(project_id="p4", area=""),
    ]
    stats = [pa.compute_stats(p, today) for p in projects]
    portfolio = pa.summarize(stats, today)
    assert portfolio.area_counts == {"health": 2, "career": 1}


def test_summarize_counts_overdue_and_stale() -> None:
    today = date(2026, 4, 22)
    projects = [
        _project(project_id="p1", target_date=date(2026, 3, 1)),  # overdue
        _project(project_id="p2", last_updated=date(2026, 2, 1)),  # stale
        _project(
            project_id="p3",
            target_date=date(2026, 3, 1),
            last_updated=date(2026, 2, 1),
        ),  # both overdue and stale
        _project(project_id="p4"),  # neither
    ]
    stats = [pa.compute_stats(p, today) for p in projects]
    portfolio = pa.summarize(stats, today)
    assert portfolio.overdue_count == 2
    assert portfolio.stale_count == 2


def test_summarize_counts_projects_without_target() -> None:
    today = date(2026, 4, 22)
    projects = [
        _project(project_id="p1", target_date=None),
        _project(project_id="p2", target_date=date(2026, 6, 1)),
        _project(project_id="p3", status="completed", target_date=None),
    ]
    stats = [pa.compute_stats(p, today) for p in projects]
    portfolio = pa.summarize(stats, today)
    # Completed projects don't count toward "no target" even without a date
    assert portfolio.no_target_count == 1


def test_summarize_counts_completions_within_30_days() -> None:
    today = date(2026, 4, 22)
    projects = [
        _project(
            project_id="p1",
            status="completed",
            last_updated=date(2026, 4, 1),  # 21 days ago
        ),
        _project(
            project_id="p2",
            status="completed",
            last_updated=date(2026, 3, 15),  # 38 days ago
        ),
        _project(
            project_id="p3",
            status="completed",
            last_updated=None,  # unknown when completed
        ),
        _project(
            project_id="p4",
            status="active",
            last_updated=date(2026, 4, 15),  # recent but not completed
        ),
    ]
    stats = [pa.compute_stats(p, today) for p in projects]
    portfolio = pa.summarize(stats, today)
    assert portfolio.completed_last_30_days == 1


def test_summarize_completion_date_in_future_is_excluded() -> None:
    today = date(2026, 4, 22)
    projects = [
        _project(
            project_id="p1",
            status="completed",
            last_updated=date(2026, 5, 1),  # future — shouldn't count
        ),
    ]
    stats = [pa.compute_stats(p, today) for p in projects]
    portfolio = pa.summarize(stats, today)
    assert portfolio.completed_last_30_days == 0


# ---------------------------------------------------------------------------
# analyze
# ---------------------------------------------------------------------------


def test_analyze_excludes_completed_by_default(tmp_path: Path) -> None:
    path = _write_projects(
        tmp_path / "projects.csv",
        [
            "p1,health,Alpha,active,,,,,,",
            "p2,health,Beta,completed,,,,,,",
        ],
    )
    stats = pa.analyze(path, today=date(2026, 4, 22))
    ids = [s.project.project_id for s in stats]
    assert ids == ["p1"]


def test_analyze_include_completed_surfaces_everything(tmp_path: Path) -> None:
    path = _write_projects(
        tmp_path / "projects.csv",
        [
            "p1,health,Alpha,active,,,,,,",
            "p2,health,Beta,completed,,,,,,",
        ],
    )
    stats = pa.analyze(path, today=date(2026, 4, 22), include_completed=True)
    ids = [s.project.project_id for s in stats]
    assert sorted(ids) == ["p1", "p2"]


def test_analyze_sorts_overdue_first_then_near_due_then_no_target(
    tmp_path: Path,
) -> None:
    path = _write_projects(
        tmp_path / "projects.csv",
        [
            "far,health,Far,active,,2026-12-01,,,,",
            "none,health,No target,active,,,,,,",
            "overdue,health,Overdue,active,,2026-03-01,,,,",
            "near,health,Near,active,,2026-05-01,,,,",
        ],
    )
    stats = pa.analyze(path, today=date(2026, 4, 22))
    ids = [s.project.project_id for s in stats]
    assert ids == ["overdue", "near", "far", "none"]


def test_analyze_with_include_completed_pushes_completed_to_end(
    tmp_path: Path,
) -> None:
    path = _write_projects(
        tmp_path / "projects.csv",
        [
            "done,health,Done,completed,,2026-01-01,,,,",
            "active,health,Active,active,,2026-05-01,,,,",
        ],
    )
    stats = pa.analyze(path, today=date(2026, 4, 22), include_completed=True)
    ids = [s.project.project_id for s in stats]
    assert ids == ["active", "done"]


def test_analyze_respects_stale_threshold(tmp_path: Path) -> None:
    path = _write_projects(
        tmp_path / "projects.csv",
        ["p1,health,Slow,active,,,,2026-04-01,,"],
    )
    lenient = pa.analyze(path, today=date(2026, 4, 22), stale_threshold_days=90)
    strict = pa.analyze(path, today=date(2026, 4, 22), stale_threshold_days=7)
    assert lenient[0].is_stale is False
    assert strict[0].is_stale is True


# ---------------------------------------------------------------------------
# format_report
# ---------------------------------------------------------------------------


def test_format_report_empty_has_friendly_message() -> None:
    portfolio = pa.summarize([], date(2026, 4, 22))
    assert pa.format_report([], portfolio) == "No projects found.\n"


def test_format_report_contains_project_name_and_summary(tmp_path: Path) -> None:
    path = _write_projects(
        tmp_path / "projects.csv",
        [
            "p1,health,Morning routine,active,2026-01-01,2026-06-01,,2026-04-10,,",
            "p2,career,Resume refresh,completed,,,,2026-04-01,,",
        ],
    )
    today = date(2026, 4, 22)
    stats = pa.analyze(path, today=today, include_completed=True)
    portfolio = pa.summarize(stats, today)
    report = pa.format_report(stats, portfolio)

    assert "Morning routine" in report
    assert "Resume refresh" in report
    assert "Total: 2" in report
    assert "active: 1" in report
    assert "completed: 1" in report
    assert "By area:" in report


def test_format_report_truncates_long_names(tmp_path: Path) -> None:
    long_name = "x" * 80
    path = _write_projects(
        tmp_path / "projects.csv",
        [f"p1,health,{long_name},active,,,,,,"],
    )
    today = date(2026, 4, 22)
    stats = pa.analyze(path, today=today)
    report = pa.format_report(stats, pa.summarize(stats, today))
    # Name should be truncated to 30 chars — not present in full
    assert long_name not in report
    assert ("x" * 30) in report


# ---------------------------------------------------------------------------
# CLI / main
# ---------------------------------------------------------------------------


def test_main_default_path_prints_no_projects(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    empty = _write_projects(tmp_path / "projects.csv", [])
    rc = pa.main(["--projects", str(empty), "--today", "2026-04-22"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "No projects found" in out


def test_main_prints_report_to_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write_projects(
        tmp_path / "projects.csv",
        ["p1,health,Alpha,active,2026-01-01,2026-06-01,,2026-04-10,,"],
    )
    rc = pa.main(["--projects", str(path), "--today", "2026-04-22"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Alpha" in out
    assert "Total: 1" in out


def test_main_include_completed_flag_shows_completed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write_projects(
        tmp_path / "projects.csv",
        [
            "p1,health,Alpha,completed,,,,2026-04-10,,",
        ],
    )
    rc = pa.main(
        [
            "--projects",
            str(path),
            "--today",
            "2026-04-22",
            "--include-completed",
        ]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "Alpha" in out


def test_main_stale_days_override(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write_projects(
        tmp_path / "projects.csv",
        ["p1,health,Slow,active,,,,2026-04-15,,"],
    )
    rc = pa.main(
        [
            "--projects",
            str(path),
            "--today",
            "2026-04-22",
            "--stale-days",
            "3",
        ]
    )
    out = capsys.readouterr().out
    assert rc == 0
    # 7 days since update with a 3-day threshold → surfaces "stale"
    assert "stale" in out


def test_main_invalid_today_raises(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        pa.main(["--today", "not-a-date"])
