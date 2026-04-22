#!/usr/bin/env python3
"""Tests for goal_analytics.py."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "01-ops" / "life-os" / "scripts"),
)

import goal_analytics as ga

GOALS_HEADER = (
    "goal_id,area,title,horizon,target_date,metric_name,"
    "metric_target,metric_current,status,last_updated,notes\n"
)


def _write_goals(path: Path, rows: list[str]) -> Path:
    path.write_text(GOALS_HEADER + "\n".join(rows) + ("\n" if rows else ""))
    return path


# ---------------------------------------------------------------------------
# Parser helpers
# ---------------------------------------------------------------------------


def test_parse_float_blank_returns_none():
    assert ga._parse_float("") is None
    assert ga._parse_float("   ") is None


def test_parse_float_invalid_returns_none():
    assert ga._parse_float("not-a-number") is None


def test_parse_float_valid():
    assert ga._parse_float("3.5") == 3.5
    assert ga._parse_float(" 7 ") == 7.0


def test_parse_date_blank_returns_none():
    assert ga._parse_date("") is None


def test_parse_date_invalid_returns_none():
    assert ga._parse_date("not-a-date") is None
    assert ga._parse_date("2026-13-40") is None


def test_parse_date_valid():
    assert ga._parse_date("2026-04-22") == date(2026, 4, 22)


def test_normalize_horizon_known_values():
    assert ga._normalize_horizon("month") == "month"
    assert ga._normalize_horizon("Quarter") == "quarter"
    assert ga._normalize_horizon(" YEAR ") == "year"


def test_normalize_horizon_unknown_returns_none():
    assert ga._normalize_horizon("decade") is None
    assert ga._normalize_horizon("") is None


# ---------------------------------------------------------------------------
# load_goals
# ---------------------------------------------------------------------------


def test_load_goals_missing_file_returns_empty(tmp_path: Path):
    assert ga.load_goals(tmp_path / "nope.csv") == []


def test_load_goals_skips_rows_without_id(tmp_path: Path):
    csv_path = _write_goals(
        tmp_path / "goals.csv",
        [
            ",health,Mystery,quarter,2026-06-30,foo,10,5,active,2026-04-01,",
            "g1,health,Sleep,quarter,2026-06-30,nights,90,30,active,2026-04-01,n",
        ],
    )
    goals = ga.load_goals(csv_path)
    assert len(goals) == 1
    assert goals[0].goal_id == "g1"


def test_load_goals_falls_back_to_id_for_missing_title(tmp_path: Path):
    csv_path = _write_goals(
        tmp_path / "goals.csv",
        ["g1,health,,quarter,2026-06-30,nights,90,30,active,2026-04-01,"],
    )
    goals = ga.load_goals(csv_path)
    assert goals[0].title == "g1"


def test_load_goals_defaults_status_to_active_when_blank(tmp_path: Path):
    csv_path = _write_goals(
        tmp_path / "goals.csv",
        ["g1,health,Sleep,quarter,2026-06-30,nights,90,30,,2026-04-01,"],
    )
    assert ga.load_goals(csv_path)[0].status == "active"


def test_load_goals_normalizes_unknown_horizon_to_none(tmp_path: Path):
    csv_path = _write_goals(
        tmp_path / "goals.csv",
        ["g1,health,Sleep,decade,2026-06-30,nights,90,30,active,2026-04-01,"],
    )
    assert ga.load_goals(csv_path)[0].horizon is None


def test_load_goals_optional_fields_become_none(tmp_path: Path):
    csv_path = _write_goals(
        tmp_path / "goals.csv",
        ["g1,health,Sleep,quarter,,,,,active,,"],
    )
    g = ga.load_goals(csv_path)[0]
    assert g.target_date is None
    assert g.metric_name is None
    assert g.metric_target is None
    assert g.metric_current is None
    assert g.last_updated is None
    assert g.notes is None


# ---------------------------------------------------------------------------
# _progress
# ---------------------------------------------------------------------------


def test_progress_none_target_returns_none():
    assert ga._progress(5.0, None) == (None, None)


def test_progress_none_current_returns_none():
    assert ga._progress(None, 10.0) == (None, None)


def test_progress_zero_target_returns_none():
    assert ga._progress(5.0, 0.0) == (None, None)


def test_progress_basic():
    percent, ratio = ga._progress(3.0, 6.0)
    assert percent == 50.0
    assert ratio == 0.5


def test_progress_caps_above_100():
    percent, ratio = ga._progress(20.0, 10.0)
    assert percent == 100.0
    assert ratio == 2.0


def test_progress_floors_at_zero_for_negative():
    percent, ratio = ga._progress(-5.0, 10.0)
    assert percent == 0.0
    assert ratio == -0.5


# ---------------------------------------------------------------------------
# _expected_progress
# ---------------------------------------------------------------------------


def _make_goal(**overrides) -> ga.Goal:
    defaults = {
        "goal_id": "g1",
        "area": "health",
        "title": "Sleep",
        "horizon": "quarter",
        "target_date": date(2026, 6, 30),
        "metric_name": "nights",
        "metric_target": 90.0,
        "metric_current": 30.0,
        "status": "active",
        "last_updated": date(2026, 4, 1),
        "notes": None,
    }
    defaults.update(overrides)
    return ga.Goal(**defaults)


def test_expected_progress_none_when_target_missing():
    g = _make_goal(target_date=None)
    assert ga._expected_progress(g, date(2026, 4, 22)) is None


def test_expected_progress_none_when_horizon_missing():
    g = _make_goal(horizon=None)
    assert ga._expected_progress(g, date(2026, 4, 22)) is None


def test_expected_progress_midpoint_of_window():
    # quarter = 90 days; midpoint should be 50%
    g = _make_goal(horizon="quarter", target_date=date(2026, 6, 30))
    midpoint = date(2026, 6, 30) - ga.timedelta(days=45)
    assert ga._expected_progress(g, midpoint) == pytest.approx(50.0)


def test_expected_progress_clamps_to_zero_before_window():
    g = _make_goal(horizon="quarter", target_date=date(2026, 6, 30))
    before = date(2026, 6, 30) - ga.timedelta(days=200)
    assert ga._expected_progress(g, before) == 0.0


def test_expected_progress_clamps_to_100_after_window():
    g = _make_goal(horizon="quarter", target_date=date(2026, 6, 30))
    after = date(2026, 6, 30) + ga.timedelta(days=10)
    assert ga._expected_progress(g, after) == 100.0


def test_expected_progress_known_horizons_all_compute():
    for horizon in ga.HORIZON_DAYS:
        g = _make_goal(horizon=horizon, target_date=date(2026, 6, 30))
        assert ga._expected_progress(g, date(2026, 4, 22)) is not None


# ---------------------------------------------------------------------------
# _status_label
# ---------------------------------------------------------------------------


def test_status_label_completed_passes_through():
    g = _make_goal(status="completed")
    assert ga._status_label(g, days_until_target=-5, ratio=0.5) == "completed"


def test_status_label_paused_passes_through():
    g = _make_goal(status="paused")
    assert ga._status_label(g, days_until_target=10, ratio=0.0) == "paused"


def test_status_label_dropped_passes_through():
    g = _make_goal(status="dropped")
    assert ga._status_label(g, days_until_target=10, ratio=0.0) == "dropped"


def test_status_label_achieved_when_metric_hit():
    g = _make_goal(status="active")
    assert ga._status_label(g, days_until_target=10, ratio=1.0) == "achieved"
    assert ga._status_label(g, days_until_target=10, ratio=1.5) == "achieved"


def test_status_label_overdue_when_target_passed():
    g = _make_goal(status="active")
    assert ga._status_label(g, days_until_target=-1, ratio=0.5) == "overdue"


def test_status_label_overdue_only_when_metric_not_hit():
    g = _make_goal(status="active")
    # ratio >= 1 wins over overdue
    assert ga._status_label(g, days_until_target=-1, ratio=1.0) == "achieved"


def test_status_label_active_default():
    g = _make_goal(status="active")
    assert ga._status_label(g, days_until_target=10, ratio=0.5) == "active"
    assert ga._status_label(g, days_until_target=None, ratio=None) == "active"


# ---------------------------------------------------------------------------
# compute_stats
# ---------------------------------------------------------------------------


def test_compute_stats_full_picture():
    g = _make_goal()
    today = date(2026, 5, 16)  # 45 days into a 90-day quarter
    s = ga.compute_stats(g, today)
    assert s.progress_percent == pytest.approx(33.333, rel=1e-3)
    assert s.progress_ratio == pytest.approx(1 / 3, rel=1e-3)
    assert s.days_until_target == (date(2026, 6, 30) - today).days
    assert s.expected_progress_percent == pytest.approx(50.0)
    assert s.on_track is False
    assert s.days_since_update == (today - date(2026, 4, 1)).days
    assert s.status_label == "active"


def test_compute_stats_on_track_when_progress_meets_expected():
    g = _make_goal(metric_current=45.0)
    today = date(2026, 5, 16)
    s = ga.compute_stats(g, today)
    assert s.on_track is True


def test_compute_stats_on_track_none_when_no_metric():
    g = _make_goal(metric_current=None, metric_target=None)
    today = date(2026, 5, 16)
    s = ga.compute_stats(g, today)
    assert s.progress_percent is None
    assert s.on_track is None


def test_compute_stats_on_track_none_when_no_horizon():
    g = _make_goal(horizon=None)
    today = date(2026, 5, 16)
    s = ga.compute_stats(g, today)
    assert s.expected_progress_percent is None
    assert s.on_track is None


def test_compute_stats_no_dates_yields_none_fields():
    g = _make_goal(target_date=None, last_updated=None, horizon=None)
    s = ga.compute_stats(g, date(2026, 5, 16))
    assert s.days_until_target is None
    assert s.days_since_update is None
    assert s.expected_progress_percent is None


def test_compute_stats_overdue_status():
    g = _make_goal(target_date=date(2026, 4, 1))
    s = ga.compute_stats(g, date(2026, 4, 22))
    assert s.days_until_target == -21
    assert s.status_label == "overdue"


def test_compute_stats_achieved_status():
    g = _make_goal(metric_current=120.0)  # 120/90 > 1
    s = ga.compute_stats(g, date(2026, 5, 16))
    assert s.progress_percent == 100.0
    assert s.progress_ratio == pytest.approx(120 / 90)
    assert s.status_label == "achieved"


# ---------------------------------------------------------------------------
# analyze
# ---------------------------------------------------------------------------


def test_analyze_uses_today_when_not_specified(tmp_path: Path):
    csv_path = _write_goals(
        tmp_path / "goals.csv",
        ["g1,health,Sleep,quarter,2026-06-30,nights,90,30,active,2026-04-01,"],
    )
    stats = ga.analyze(csv_path)
    assert len(stats) == 1
    assert stats[0].goal.goal_id == "g1"
    # days_until_target should be computed against today (real date)
    assert stats[0].days_until_target == (date(2026, 6, 30) - date.today()).days


def test_analyze_excludes_completed_and_dropped_by_default(tmp_path: Path):
    csv_path = _write_goals(
        tmp_path / "goals.csv",
        [
            "g1,health,Active goal,quarter,2026-06-30,nights,90,30,active,2026-04-01,",
            "g2,work,Done goal,quarter,2026-06-30,nights,90,90,completed,2026-04-01,",
            "g3,study,Quit goal,quarter,2026-06-30,nights,90,5,dropped,2026-04-01,",
            "g4,health,Paused goal,quarter,2026-06-30,nights,90,5,paused,2026-04-01,",
        ],
    )
    stats = ga.analyze(csv_path, today=date(2026, 4, 22))
    ids = [s.goal.goal_id for s in stats]
    assert "g1" in ids
    assert "g4" in ids  # paused is included (not terminal)
    assert "g2" not in ids
    assert "g3" not in ids


def test_analyze_include_inactive_returns_all(tmp_path: Path):
    csv_path = _write_goals(
        tmp_path / "goals.csv",
        [
            "g1,health,Active,quarter,2026-06-30,nights,90,30,active,2026-04-01,",
            "g2,work,Done,quarter,2026-06-30,nights,90,90,completed,2026-04-01,",
        ],
    )
    stats = ga.analyze(csv_path, today=date(2026, 4, 22), include_inactive=True)
    assert {s.goal.goal_id for s in stats} == {"g1", "g2"}


def test_analyze_sort_order(tmp_path: Path):
    csv_path = _write_goals(
        tmp_path / "goals.csv",
        [
            # active, far future (60 days)
            "g_far,health,Far,quarter,2026-06-21,nights,90,30,active,2026-04-01,",
            # active, no target_date — should land last among active
            "g_none,work,None,quarter,,nights,90,30,active,2026-04-01,",
            # active, overdue (-10)
            "g_over,study,Overdue,quarter,2026-04-12,nights,90,30,active,2026-04-01,",
            # active, near future (5)
            "g_near,health,Near,quarter,2026-04-27,nights,90,30,active,2026-04-01,",
            # paused, near future — should sort after all actives
            "g_pause,health,Apaused,quarter,2026-04-27,nights,90,30,paused,2026-04-01,",
        ],
    )
    stats = ga.analyze(csv_path, today=date(2026, 4, 22))
    ids = [s.goal.goal_id for s in stats]
    # active first, ascending days_until_target, no-target last among actives
    assert ids == ["g_over", "g_near", "g_far", "g_none", "g_pause"]


def test_analyze_sort_breaks_ties_alphabetically(tmp_path: Path):
    csv_path = _write_goals(
        tmp_path / "goals.csv",
        [
            "g1,health,Banana,quarter,2026-04-27,nights,90,30,active,2026-04-01,",
            "g2,health,Apple,quarter,2026-04-27,nights,90,30,active,2026-04-01,",
        ],
    )
    stats = ga.analyze(csv_path, today=date(2026, 4, 22))
    assert [s.goal.title for s in stats] == ["Apple", "Banana"]


# ---------------------------------------------------------------------------
# format_report
# ---------------------------------------------------------------------------


def test_format_report_empty_stats():
    assert ga.format_report([]) == "No goals found.\n"


def test_format_report_renders_columns(tmp_path: Path):
    csv_path = _write_goals(
        tmp_path / "goals.csv",
        ["g1,health,Sleep,quarter,2026-06-30,nights,90,30,active,2026-04-01,"],
    )
    stats = ga.analyze(csv_path, today=date(2026, 5, 16))
    report = ga.format_report(stats)
    assert "Sleep" in report
    assert "health" in report
    assert "active" in report
    assert "33.3%" in report
    assert "50.0%" in report
    assert "no" in report  # on-track


def test_format_report_handles_none_fields(tmp_path: Path):
    csv_path = _write_goals(
        tmp_path / "goals.csv",
        ["g1,health,No metric,,,,,,active,,"],
    )
    stats = ga.analyze(csv_path, today=date(2026, 4, 22))
    report = ga.format_report(stats)
    # progress, expected, on-track, days-left, stale all rendered as dashes
    assert "No metric" in report
    assert "-" in report


def test_format_report_truncates_long_titles(tmp_path: Path):
    long_title = "X" * 80
    csv_path = _write_goals(
        tmp_path / "goals.csv",
        [f"g1,health,{long_title},quarter,2026-06-30,nights,90,30,active,2026-04-01,"],
    )
    stats = ga.analyze(csv_path, today=date(2026, 4, 22))
    report = ga.format_report(stats)
    # Truncated to 30 chars in the title column
    assert "X" * 30 in report
    assert "X" * 31 not in report


# ---------------------------------------------------------------------------
# CLI / main
# ---------------------------------------------------------------------------


def test_main_default_paths(tmp_path: Path, capsys, monkeypatch):
    csv_path = _write_goals(
        tmp_path / "goals.csv",
        ["g1,health,Sleep,quarter,2026-06-30,nights,90,30,active,2026-04-01,"],
    )
    rc = ga.main(["--goals", str(csv_path), "--today", "2026-05-16"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Sleep" in out
    assert "33.3%" in out


def test_main_include_inactive_flag(tmp_path: Path, capsys):
    csv_path = _write_goals(
        tmp_path / "goals.csv",
        [
            "g1,health,Active,quarter,2026-06-30,nights,90,30,active,2026-04-01,",
            "g2,work,Done,quarter,2026-06-30,nights,90,90,completed,2026-04-01,",
        ],
    )
    ga.main(
        [
            "--goals",
            str(csv_path),
            "--today",
            "2026-05-16",
            "--include-inactive",
        ]
    )
    out = capsys.readouterr().out
    assert "Active" in out
    assert "Done" in out


def test_main_empty_goals_renders_no_goals_message(tmp_path: Path, capsys):
    csv_path = _write_goals(tmp_path / "goals.csv", [])
    ga.main(["--goals", str(csv_path), "--today", "2026-05-16"])
    out = capsys.readouterr().out
    assert "No goals found." in out


def test_module_runs_against_canonical_data():
    """The script should produce a non-empty report for the checked-in data."""
    repo_root = Path(__file__).resolve().parents[1]
    csv_path = repo_root / "01-ops" / "life-os" / "data" / "canonical" / "goals.csv"
    assert csv_path.exists(), "canonical goals.csv missing"
    stats = ga.analyze(csv_path, today=date(2026, 4, 22))
    # at least the example goal should be present
    assert len(stats) >= 1
    report = ga.format_report(stats)
    assert "Goal" in report  # header rendered
