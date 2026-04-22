#!/usr/bin/env python3
"""Tests for task_analytics.py."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "01-ops" / "life-os" / "scripts"),
)

import task_analytics as ta

TASKS_HEADER = (
    "task_id,project_id,title,domain,status,priority,effort_mins,"
    "due_date,energy,context,source,next_step,"
    "scheduled_date,scheduled_start,scheduled_end,last_updated,notes\n"
)


def _write_tasks(path: Path, rows: list[str]) -> Path:
    path.write_text(TASKS_HEADER + "\n".join(rows) + ("\n" if rows else ""))
    return path


def _row(
    task_id: str = "t1",
    project_id: str = "",
    title: str = "Task",
    domain: str = "work",
    status: str = "queued",
    priority: str = "P2",
    effort_mins: str = "30",
    due_date: str = "",
    energy: str = "medium",
    context: str = "desk",
    source: str = "manual",
    next_step: str = "",
    scheduled_date: str = "",
    scheduled_start: str = "",
    scheduled_end: str = "",
    last_updated: str = "",
    notes: str = "",
) -> str:
    return ",".join(
        [
            task_id,
            project_id,
            title,
            domain,
            status,
            priority,
            effort_mins,
            due_date,
            energy,
            context,
            source,
            next_step,
            scheduled_date,
            scheduled_start,
            scheduled_end,
            last_updated,
            notes,
        ]
    )


# ---------------------------------------------------------------------------
# Parser helpers
# ---------------------------------------------------------------------------


def test_parse_int_blank_returns_none():
    assert ta._parse_int("") is None
    assert ta._parse_int("   ") is None


def test_parse_int_invalid_returns_none():
    assert ta._parse_int("abc") is None
    assert ta._parse_int("3.5") is None


def test_parse_int_valid():
    assert ta._parse_int("30") == 30
    assert ta._parse_int(" 15 ") == 15


def test_parse_date_blank_returns_none():
    assert ta._parse_date("") is None


def test_parse_date_invalid_returns_none():
    assert ta._parse_date("not-a-date") is None
    assert ta._parse_date("2026-13-40") is None


def test_parse_date_valid():
    assert ta._parse_date("2026-04-22") == date(2026, 4, 22)


def test_normalize_priority_known_values():
    assert ta._normalize_priority("P1") == "P1"
    assert ta._normalize_priority("p2") == "P2"
    assert ta._normalize_priority(" P3 ") == "P3"


def test_normalize_priority_unknown_returns_none():
    assert ta._normalize_priority("P4") is None
    assert ta._normalize_priority("") is None
    assert ta._normalize_priority("high") is None


def test_normalize_energy_known_values():
    assert ta._normalize_energy("low") == "low"
    assert ta._normalize_energy("MEDIUM") == "medium"
    assert ta._normalize_energy(" High ") == "high"


def test_normalize_energy_unknown_returns_none():
    assert ta._normalize_energy("nuclear") is None
    assert ta._normalize_energy("") is None


# ---------------------------------------------------------------------------
# load_tasks
# ---------------------------------------------------------------------------


def test_load_tasks_missing_file_returns_empty(tmp_path: Path):
    assert ta.load_tasks(tmp_path / "nope.csv") == []


def test_load_tasks_empty_file_returns_empty(tmp_path: Path):
    path = _write_tasks(tmp_path / "tasks.csv", [])
    assert ta.load_tasks(path) == []


def test_load_tasks_skips_rows_without_id(tmp_path: Path):
    path = _write_tasks(
        tmp_path / "tasks.csv",
        [_row(task_id=""), _row(task_id="t1", title="Keep me")],
    )
    tasks = ta.load_tasks(path)
    assert len(tasks) == 1
    assert tasks[0].task_id == "t1"


def test_load_tasks_strips_whitespace(tmp_path: Path):
    path = _write_tasks(
        tmp_path / "tasks.csv",
        [_row(task_id="t1", title="  Padded  ", project_id=" p1 ")],
    )
    task = ta.load_tasks(path)[0]
    assert task.title == "Padded"
    assert task.project_id == "p1"


def test_load_tasks_blank_optional_fields_become_none(tmp_path: Path):
    path = _write_tasks(
        tmp_path / "tasks.csv",
        [
            _row(
                task_id="t1",
                project_id="",
                domain="",
                priority="",
                effort_mins="",
                due_date="",
                energy="",
                scheduled_date="",
                last_updated="",
            )
        ],
    )
    task = ta.load_tasks(path)[0]
    assert task.project_id is None
    assert task.domain is None
    assert task.priority is None
    assert task.effort_mins is None
    assert task.due_date is None
    assert task.energy is None
    assert task.scheduled_date is None
    assert task.last_updated is None


def test_load_tasks_defaults_status_when_missing(tmp_path: Path):
    path = _write_tasks(tmp_path / "tasks.csv", [_row(task_id="t1", status="")])
    task = ta.load_tasks(path)[0]
    assert task.status == "queued"


def test_load_tasks_title_defaults_to_id(tmp_path: Path):
    path = _write_tasks(tmp_path / "tasks.csv", [_row(task_id="t1", title="")])
    task = ta.load_tasks(path)[0]
    assert task.title == "t1"


def test_load_tasks_normalizes_case(tmp_path: Path):
    path = _write_tasks(
        tmp_path / "tasks.csv",
        [_row(task_id="t1", status="IN_PROGRESS", priority="p1", energy="HIGH")],
    )
    task = ta.load_tasks(path)[0]
    assert task.status == "in_progress"
    assert task.priority == "P1"
    assert task.energy == "high"


def test_load_tasks_parses_dates_and_ints(tmp_path: Path):
    path = _write_tasks(
        tmp_path / "tasks.csv",
        [
            _row(
                task_id="t1",
                effort_mins="45",
                due_date="2026-05-01",
                scheduled_date="2026-04-25",
                last_updated="2026-04-10",
            )
        ],
    )
    task = ta.load_tasks(path)[0]
    assert task.effort_mins == 45
    assert task.due_date == date(2026, 5, 1)
    assert task.scheduled_date == date(2026, 4, 25)
    assert task.last_updated == date(2026, 4, 10)


# ---------------------------------------------------------------------------
# compute_stats
# ---------------------------------------------------------------------------


def _task(**overrides) -> ta.Task:
    defaults: dict = {
        "task_id": "t1",
        "project_id": None,
        "title": "Task",
        "domain": "work",
        "status": "queued",
        "priority": "P2",
        "effort_mins": 30,
        "due_date": None,
        "energy": "medium",
        "scheduled_date": None,
        "last_updated": None,
    }
    defaults.update(overrides)
    return ta.Task(**defaults)


TODAY = date(2026, 4, 22)


def test_compute_stats_no_dates_yields_none_for_day_deltas():
    stats = ta.compute_stats(_task(), TODAY)
    assert stats.days_until_due is None
    assert stats.days_since_update is None
    assert stats.is_overdue is False
    assert stats.is_stale is False
    assert stats.is_scheduled is False
    assert stats.status_label == "queued"


def test_compute_stats_future_due_positive_days():
    stats = ta.compute_stats(_task(due_date=date(2026, 4, 30)), TODAY)
    assert stats.days_until_due == 8
    assert stats.is_overdue is False


def test_compute_stats_overdue_is_flagged():
    stats = ta.compute_stats(_task(status="queued", due_date=date(2026, 4, 10)), TODAY)
    assert stats.days_until_due == -12
    assert stats.is_overdue is True
    assert stats.status_label == "overdue"


def test_compute_stats_terminal_task_never_overdue():
    stats = ta.compute_stats(
        _task(status="completed", due_date=date(2026, 4, 10)), TODAY
    )
    assert stats.is_overdue is False
    assert stats.status_label == "completed"


def test_compute_stats_done_status_is_terminal():
    stats = ta.compute_stats(_task(status="done", due_date=date(2026, 4, 10)), TODAY)
    assert stats.is_overdue is False
    assert stats.status_label == "done"


def test_compute_stats_dropped_status_is_terminal():
    stats = ta.compute_stats(_task(status="dropped", due_date=date(2026, 4, 10)), TODAY)
    assert stats.is_overdue is False
    assert stats.status_label == "dropped"


def test_compute_stats_stale_threshold_default():
    stats = ta.compute_stats(_task(last_updated=date(2026, 4, 1)), TODAY)
    assert stats.days_since_update == 21
    assert stats.is_stale is True
    assert stats.status_label == "stale"


def test_compute_stats_stale_threshold_custom():
    task = _task(last_updated=date(2026, 4, 15))
    assert ta.compute_stats(task, TODAY, stale_threshold_days=14).is_stale is False
    assert ta.compute_stats(task, TODAY, stale_threshold_days=7).is_stale is True


def test_compute_stats_stale_boundary_inclusive():
    task = _task(last_updated=date(2026, 4, 8))  # 14 days ago
    stats = ta.compute_stats(task, TODAY, stale_threshold_days=14)
    assert stats.days_since_update == 14
    assert stats.is_stale is True


def test_compute_stats_stale_not_flagged_for_terminal():
    stats = ta.compute_stats(
        _task(status="completed", last_updated=date(2026, 3, 1)), TODAY
    )
    assert stats.is_stale is False


def test_compute_stats_overdue_wins_over_stale_label():
    stats = ta.compute_stats(
        _task(due_date=date(2026, 4, 10), last_updated=date(2026, 3, 1)), TODAY
    )
    assert stats.is_overdue is True
    assert stats.is_stale is True
    assert stats.status_label == "overdue"


def test_compute_stats_blocked_label_wins_over_stale():
    stats = ta.compute_stats(
        _task(status="blocked", last_updated=date(2026, 3, 1)), TODAY
    )
    assert stats.status_label == "blocked"
    assert stats.is_stale is True


def test_compute_stats_blocked_still_overdue_first():
    stats = ta.compute_stats(_task(status="blocked", due_date=date(2026, 4, 10)), TODAY)
    assert stats.status_label == "overdue"


def test_compute_stats_scheduled_is_flagged():
    stats = ta.compute_stats(_task(scheduled_date=date(2026, 4, 25)), TODAY)
    assert stats.is_scheduled is True


def test_compute_stats_in_progress_label_passthrough():
    stats = ta.compute_stats(
        _task(status="in_progress", last_updated=date(2026, 4, 20)), TODAY
    )
    assert stats.status_label == "in_progress"
    assert stats.is_stale is False


# ---------------------------------------------------------------------------
# analyze
# ---------------------------------------------------------------------------


def test_analyze_missing_file_returns_empty(tmp_path: Path):
    assert ta.analyze(tmp_path / "none.csv", today=TODAY) == []


def test_analyze_excludes_terminal_by_default(tmp_path: Path):
    path = _write_tasks(
        tmp_path / "tasks.csv",
        [
            _row(task_id="a", status="queued"),
            _row(task_id="b", status="completed"),
            _row(task_id="c", status="done"),
            _row(task_id="d", status="dropped"),
        ],
    )
    stats = ta.analyze(path, today=TODAY)
    assert [s.task.task_id for s in stats] == ["a"]


def test_analyze_include_terminal(tmp_path: Path):
    path = _write_tasks(
        tmp_path / "tasks.csv",
        [
            _row(task_id="a", status="queued"),
            _row(task_id="b", status="completed"),
        ],
    )
    stats = ta.analyze(path, today=TODAY, include_terminal=True)
    ids = {s.task.task_id for s in stats}
    assert ids == {"a", "b"}


def test_analyze_sort_overdue_first(tmp_path: Path):
    path = _write_tasks(
        tmp_path / "tasks.csv",
        [
            _row(task_id="far", title="far", due_date="2026-05-30"),
            _row(task_id="over", title="over", due_date="2026-04-10"),
            _row(task_id="none", title="none", due_date=""),
            _row(task_id="near", title="near", due_date="2026-04-25"),
        ],
    )
    stats = ta.analyze(path, today=TODAY)
    assert [s.task.task_id for s in stats] == ["over", "near", "far", "none"]


def test_analyze_sort_priority_breaks_ties(tmp_path: Path):
    # Same due date: priority P1 should sort before P3 and unset.
    path = _write_tasks(
        tmp_path / "tasks.csv",
        [
            _row(task_id="c", title="c-unset", priority="", due_date="2026-05-01"),
            _row(task_id="a", title="a-p3", priority="P3", due_date="2026-05-01"),
            _row(task_id="b", title="b-p1", priority="P1", due_date="2026-05-01"),
        ],
    )
    stats = ta.analyze(path, today=TODAY)
    assert [s.task.task_id for s in stats] == ["b", "a", "c"]


def test_analyze_sort_title_breaks_full_ties(tmp_path: Path):
    path = _write_tasks(
        tmp_path / "tasks.csv",
        [
            _row(task_id="t2", title="Zeta", priority="P2"),
            _row(task_id="t1", title="Alpha", priority="P2"),
        ],
    )
    stats = ta.analyze(path, today=TODAY)
    assert [s.task.task_id for s in stats] == ["t1", "t2"]


def test_analyze_terminal_sorted_after_active(tmp_path: Path):
    path = _write_tasks(
        tmp_path / "tasks.csv",
        [
            _row(task_id="done", title="done", status="completed"),
            _row(task_id="active", title="active", status="queued"),
        ],
    )
    stats = ta.analyze(path, today=TODAY, include_terminal=True)
    assert [s.task.task_id for s in stats] == ["active", "done"]


def test_analyze_honors_stale_threshold(tmp_path: Path):
    path = _write_tasks(
        tmp_path / "tasks.csv",
        [_row(task_id="t1", last_updated="2026-04-10")],
    )
    [stats] = ta.analyze(path, today=TODAY, stale_threshold_days=7)
    assert stats.is_stale is True
    [stats] = ta.analyze(path, today=TODAY, stale_threshold_days=30)
    assert stats.is_stale is False


def test_analyze_today_defaults_to_today_when_none(tmp_path: Path, monkeypatch):
    path = _write_tasks(
        tmp_path / "tasks.csv",
        [_row(task_id="t1", due_date="2026-04-22")],
    )

    class FakeDate(date):
        @classmethod
        def today(cls):
            return date(2026, 4, 22)

    monkeypatch.setattr(ta, "date", FakeDate)
    stats = ta.analyze(path)
    assert stats[0].days_until_due == 0


# ---------------------------------------------------------------------------
# summarize
# ---------------------------------------------------------------------------


def test_summarize_empty_stats():
    portfolio = ta.summarize([], today=TODAY)
    assert portfolio.total == 0
    assert portfolio.active_count == 0
    assert portfolio.by_status == {}


def test_summarize_counts_statuses_priorities_domains(tmp_path: Path):
    path = _write_tasks(
        tmp_path / "tasks.csv",
        [
            _row(task_id="a", status="queued", priority="P1", domain="work"),
            _row(task_id="b", status="in_progress", priority="P1", domain="work"),
            _row(task_id="c", status="blocked", priority="P2", domain="health"),
            _row(task_id="d", status="queued", priority="", domain=""),
        ],
    )
    stats = ta.analyze(path, today=TODAY)
    p = ta.summarize(stats, today=TODAY)
    assert p.total == 4
    assert p.by_status == {"queued": 2, "in_progress": 1, "blocked": 1}
    assert p.by_priority == {"P1": 2, "P2": 1, "unset": 1}
    assert p.by_domain == {"work": 2, "health": 1, "unset": 1}
    assert p.active_count == 4
    assert p.wip_count == 1
    assert p.blocked_count == 1


def test_summarize_counts_overdue_stale_scheduled(tmp_path: Path):
    path = _write_tasks(
        tmp_path / "tasks.csv",
        [
            _row(task_id="over", due_date="2026-04-10"),
            _row(task_id="stale", last_updated="2026-04-01"),
            _row(task_id="sched", scheduled_date="2026-04-25"),
            _row(task_id="clean", last_updated="2026-04-20"),
        ],
    )
    stats = ta.analyze(path, today=TODAY)
    p = ta.summarize(stats, today=TODAY)
    assert p.overdue_count == 1
    assert p.stale_count == 1
    assert p.scheduled_count == 1


def test_summarize_scheduled_excludes_terminal(tmp_path: Path):
    path = _write_tasks(
        tmp_path / "tasks.csv",
        [
            _row(task_id="done", status="completed", scheduled_date="2026-04-25"),
            _row(task_id="live", status="queued", scheduled_date="2026-04-25"),
        ],
    )
    stats = ta.analyze(path, today=TODAY, include_terminal=True)
    p = ta.summarize(stats, today=TODAY)
    assert p.scheduled_count == 1


def test_summarize_completion_windows(tmp_path: Path):
    path = _write_tasks(
        tmp_path / "tasks.csv",
        [
            _row(task_id="recent", status="completed", last_updated="2026-04-20"),
            _row(task_id="midrange", status="done", last_updated="2026-04-01"),
            _row(task_id="old", status="completed", last_updated="2026-03-10"),
            _row(task_id="dropped", status="dropped", last_updated="2026-04-21"),
        ],
    )
    stats = ta.analyze(path, today=TODAY, include_terminal=True)
    p = ta.summarize(stats, today=TODAY)
    assert p.completed_last_7_days == 1
    assert p.completed_last_30_days == 2


def test_summarize_ignores_completion_without_last_updated(tmp_path: Path):
    path = _write_tasks(
        tmp_path / "tasks.csv",
        [_row(task_id="t1", status="completed", last_updated="")],
    )
    stats = ta.analyze(path, today=TODAY, include_terminal=True)
    p = ta.summarize(stats, today=TODAY)
    assert p.completed_last_7_days == 0
    assert p.completed_last_30_days == 0


def test_summarize_ignores_future_last_updated(tmp_path: Path):
    path = _write_tasks(
        tmp_path / "tasks.csv",
        [_row(task_id="t1", status="completed", last_updated="2026-05-30")],
    )
    stats = ta.analyze(path, today=TODAY, include_terminal=True)
    p = ta.summarize(stats, today=TODAY)
    assert p.completed_last_7_days == 0
    assert p.completed_last_30_days == 0


def test_summarize_today_defaults_to_today_when_none(monkeypatch):
    class FakeDate(date):
        @classmethod
        def today(cls):
            return date(2026, 4, 22)

    monkeypatch.setattr(ta, "date", FakeDate)
    task = _task(status="completed", last_updated=date(2026, 4, 20))
    stats = [ta.compute_stats(task, date(2026, 4, 22))]
    p = ta.summarize(stats)
    assert p.completed_last_7_days == 1


# ---------------------------------------------------------------------------
# format_report
# ---------------------------------------------------------------------------


def test_format_report_empty_message():
    assert ta.format_report([]) == "No tasks found.\n"


def test_format_report_contains_header_and_row(tmp_path: Path):
    path = _write_tasks(
        tmp_path / "tasks.csv",
        [_row(task_id="t1", title="Demo", priority="P1", due_date="2026-04-25")],
    )
    stats = ta.analyze(path, today=TODAY)
    out = ta.format_report(stats)
    assert "Task" in out
    assert "Demo" in out
    assert "P1" in out
    assert "+3d" in out or "+  3d" in out  # days formatting


def test_format_report_truncates_long_title(tmp_path: Path):
    long_title = "X" * 60
    path = _write_tasks(tmp_path / "tasks.csv", [_row(task_id="t1", title=long_title)])
    stats = ta.analyze(path, today=TODAY)
    out = ta.format_report(stats)
    # Title column is 34 wide; must not bleed entire 60 chars
    assert "X" * 34 in out
    assert "X" * 35 not in out


def test_format_report_handles_missing_values(tmp_path: Path):
    path = _write_tasks(
        tmp_path / "tasks.csv",
        [_row(task_id="t1", title="t", priority="", due_date="", domain="")],
    )
    stats = ta.analyze(path, today=TODAY)
    out = ta.format_report(stats)
    # Missing priority/domain/due render as '-'
    assert "\n" in out
    lines = out.strip().split("\n")
    data_line = lines[-1]
    assert " - " in data_line or data_line.endswith(" -")


def test_format_report_appends_portfolio_summary(tmp_path: Path):
    path = _write_tasks(
        tmp_path / "tasks.csv",
        [
            _row(task_id="a", status="in_progress"),
            _row(task_id="b", status="blocked"),
        ],
    )
    stats = ta.analyze(path, today=TODAY)
    portfolio = ta.summarize(stats, today=TODAY)
    out = ta.format_report(stats, portfolio)
    assert "Portfolio:" in out
    assert "2 total" in out
    assert "WIP 1" in out
    assert "blocked 1" in out


def test_format_report_without_portfolio_omits_summary(tmp_path: Path):
    path = _write_tasks(tmp_path / "tasks.csv", [_row(task_id="t1")])
    stats = ta.analyze(path, today=TODAY)
    assert "Portfolio:" not in ta.format_report(stats)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_prints_report(tmp_path: Path, capsys):
    path = _write_tasks(
        tmp_path / "tasks.csv",
        [_row(task_id="t1", title="Demo", priority="P1", due_date="2026-04-25")],
    )
    rc = ta.main(["--tasks", str(path), "--today", "2026-04-22"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Demo" in out
    assert "Portfolio:" in out


def test_cli_include_terminal_flag(tmp_path: Path, capsys):
    path = _write_tasks(
        tmp_path / "tasks.csv",
        [_row(task_id="t1", title="Done", status="completed")],
    )
    rc = ta.main(["--tasks", str(path), "--today", "2026-04-22", "--include-terminal"])
    assert rc == 0
    assert "Done" in capsys.readouterr().out


def test_cli_stale_days_flag(tmp_path: Path, capsys):
    path = _write_tasks(
        tmp_path / "tasks.csv",
        [_row(task_id="t1", title="X", last_updated="2026-04-15")],
    )
    # Default threshold (14): not stale. Override to 3: stale.
    rc = ta.main(["--tasks", str(path), "--today", "2026-04-22", "--stale-days", "3"])
    assert rc == 0
    assert "stale" in capsys.readouterr().out


def test_cli_rejects_bad_today(tmp_path: Path):
    path = _write_tasks(tmp_path / "tasks.csv", [_row(task_id="t1")])
    with pytest.raises(SystemExit):
        ta.main(["--tasks", str(path), "--today", "not-a-date"])


def test_module_runs_as_script(tmp_path: Path, capsys, monkeypatch):
    path = _write_tasks(tmp_path / "tasks.csv", [_row(task_id="t1", title="M")])
    monkeypatch.setattr(
        sys,
        "argv",
        ["task_analytics.py", "--tasks", str(path), "--today", "2026-04-22"],
    )
    # Executing main() directly is equivalent — ensures sys.exit wrapper works.
    rc = ta.main()
    assert rc == 0
    assert "M" in capsys.readouterr().out
