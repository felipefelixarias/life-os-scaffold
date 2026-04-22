"""Tests for ``archive_completed`` — terminal-row archival utility."""

from __future__ import annotations

import csv
import sys
from datetime import date
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "01-ops" / "life-os" / "scripts" / "archive_completed.py"
SPEC = spec_from_file_location("archive_completed", MODULE_PATH)
assert SPEC is not None
archive_completed = module_from_spec(SPEC)
# Register in sys.modules BEFORE exec_module so the @dataclass decorator in the
# target module can resolve cls.__module__ via the loader's module cache.
sys.modules["archive_completed"] = archive_completed
assert SPEC.loader is not None
SPEC.loader.exec_module(archive_completed)

ArchivePlan = archive_completed.ArchivePlan
TERMINAL_STATUSES = archive_completed.TERMINAL_STATUSES
AGE_FIELDS = archive_completed.AGE_FIELDS
DEFAULT_MIN_AGE_DAYS = archive_completed.DEFAULT_MIN_AGE_DAYS
supported_files = archive_completed.supported_files
plan_archive = archive_completed.plan_archive
apply_plan = archive_completed.apply_plan
archive_file = archive_completed.archive_file
archive_all = archive_completed.archive_all
format_plan = archive_completed.format_plan
main = archive_completed.main


TASKS_HEADER = [
    "task_id",
    "project_id",
    "title",
    "domain",
    "status",
    "priority",
    "effort_mins",
    "due_date",
    "energy",
    "context",
    "source",
    "next_step",
    "scheduled_date",
    "scheduled_start",
    "scheduled_end",
    "last_updated",
    "notes",
]

PROJECTS_HEADER = [
    "project_id",
    "area",
    "name",
    "status",
    "start_date",
    "target_date",
    "description",
    "last_updated",
    "notes",
    "active",
]

GOALS_HEADER = [
    "goal_id",
    "area",
    "title",
    "horizon",
    "target_date",
    "metric_name",
    "metric_target",
    "metric_current",
    "status",
    "last_updated",
    "notes",
]

TIME_BLOCKS_HEADER = [
    "block_id",
    "date",
    "start",
    "end",
    "title",
    "domain",
    "task_id",
    "source",
    "status",
    "notes",
]


def _task_row(
    task_id: str, status: str, last_updated: str, title: str = "T"
) -> dict[str, str]:
    row = dict.fromkeys(TASKS_HEADER, "")
    row["task_id"] = task_id
    row["title"] = title
    row["status"] = status
    row["last_updated"] = last_updated
    return row


def _write_csv(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        for row in rows:
            writer.writerow({h: row.get(h, "") for h in header})


def _read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = [dict(zip(header, r, strict=True)) for r in reader]
    return header, rows


# ---------------------------------------------------------------------------
# Constants / module surface
# ---------------------------------------------------------------------------


def test_supported_files_matches_terminal_statuses() -> None:
    assert supported_files() == set(TERMINAL_STATUSES.keys())


def test_supported_files_is_the_expected_four() -> None:
    assert supported_files() == {
        "tasks.csv",
        "goals.csv",
        "projects.csv",
        "time_blocks.csv",
    }


def test_age_fields_covers_all_supported_files() -> None:
    assert set(AGE_FIELDS.keys()) == supported_files()


def test_terminal_statuses_disjoint_from_active_statuses() -> None:
    # Sanity: e.g. 'in_progress' must never count as terminal for tasks.
    assert "in_progress" not in TERMINAL_STATUSES["tasks.csv"]
    assert "planned" not in TERMINAL_STATUSES["time_blocks.csv"]
    assert "active" not in TERMINAL_STATUSES["goals.csv"]
    assert "planning" not in TERMINAL_STATUSES["projects.csv"]


# ---------------------------------------------------------------------------
# plan_archive: filtering logic
# ---------------------------------------------------------------------------


def test_plan_archive_keeps_non_terminal_rows(tmp_path: Path) -> None:
    source = tmp_path / "tasks.csv"
    _write_csv(
        source,
        TASKS_HEADER,
        [
            _task_row("t1", "in_progress", "2020-01-01"),
            _task_row("t2", "queued", "2020-01-01"),
            _task_row("t3", "blocked", "2020-01-01"),
        ],
    )
    plan = plan_archive(
        source,
        archive_dir=tmp_path / "archive",
        today=date(2026, 4, 22),
        min_age_days=90,
    )
    assert plan.archive_count == 0
    assert plan.keep_count == 3
    assert plan.buckets == {}


def test_plan_archive_aged_terminal_rows_move(tmp_path: Path) -> None:
    source = tmp_path / "tasks.csv"
    _write_csv(
        source,
        TASKS_HEADER,
        [
            _task_row("old_done", "done", "2025-01-01"),
            _task_row("old_dropped", "dropped", "2024-06-15"),
            _task_row("old_completed", "completed", "2025-12-31"),
            _task_row("fresh_done", "done", "2026-04-01"),
            _task_row("active", "in_progress", "2026-04-10"),
        ],
    )
    plan = plan_archive(
        source,
        archive_dir=tmp_path / "archive",
        today=date(2026, 4, 22),
        min_age_days=90,
    )
    assert plan.archive_count == 3
    assert plan.keep_count == 2
    assert set(plan.buckets.keys()) == {"2024", "2025"}
    assert len(plan.buckets["2025"]) == 2
    assert len(plan.buckets["2024"]) == 1


def test_plan_archive_boundary_exactly_min_age(tmp_path: Path) -> None:
    """min_age_days is inclusive: exactly-N-days-old rows ARE archived."""
    source = tmp_path / "tasks.csv"
    today = date(2026, 4, 22)
    exactly_90 = "2026-01-22"
    day_89 = "2026-01-23"
    _write_csv(
        source,
        TASKS_HEADER,
        [
            _task_row("at_boundary", "done", exactly_90),
            _task_row("one_day_younger", "done", day_89),
        ],
    )
    plan = plan_archive(
        source, archive_dir=tmp_path / "arc", today=today, min_age_days=90
    )
    archived_ids = {r["task_id"] for rows in plan.buckets.values() for r in rows}
    assert archived_ids == {"at_boundary"}
    kept_ids = {r["task_id"] for r in plan.rows_to_keep}
    assert kept_ids == {"one_day_younger"}


def test_plan_archive_undated_kept_by_default(tmp_path: Path) -> None:
    source = tmp_path / "tasks.csv"
    _write_csv(
        source,
        TASKS_HEADER,
        [
            _task_row("no_date", "done", ""),
            _task_row("bad_date", "done", "not-a-date"),
        ],
    )
    plan = plan_archive(
        source,
        archive_dir=tmp_path / "arc",
        today=date(2026, 4, 22),
        min_age_days=90,
        archive_undated=False,
    )
    assert plan.archive_count == 0
    assert plan.keep_count == 2


def test_plan_archive_undated_archives_with_flag(tmp_path: Path) -> None:
    source = tmp_path / "tasks.csv"
    _write_csv(
        source,
        TASKS_HEADER,
        [
            _task_row("no_date", "done", ""),
            _task_row("bad_date", "dropped", "not-a-date"),
            _task_row("dated", "done", "2024-01-01"),
        ],
    )
    plan = plan_archive(
        source,
        archive_dir=tmp_path / "arc",
        today=date(2026, 4, 22),
        min_age_days=90,
        archive_undated=True,
    )
    assert plan.archive_count == 3
    assert plan.keep_count == 0
    assert len(plan.buckets["undated"]) == 2
    assert len(plan.buckets["2024"]) == 1


def test_plan_archive_empty_status_is_kept(tmp_path: Path) -> None:
    source = tmp_path / "tasks.csv"
    _write_csv(
        source,
        TASKS_HEADER,
        [_task_row("noop", "", "2020-01-01")],
    )
    plan = plan_archive(source, archive_dir=tmp_path / "arc", today=date(2026, 4, 22))
    assert plan.archive_count == 0
    assert plan.keep_count == 1


def test_plan_archive_missing_file_returns_empty_plan(tmp_path: Path) -> None:
    source = tmp_path / "tasks.csv"
    plan = plan_archive(source, archive_dir=tmp_path / "arc", today=date(2026, 4, 22))
    assert plan.header == []
    assert plan.rows_to_keep == []
    assert plan.buckets == {}


def test_plan_archive_empty_file_returns_empty_plan(tmp_path: Path) -> None:
    source = tmp_path / "tasks.csv"
    source.write_text("", encoding="utf-8")
    plan = plan_archive(source, archive_dir=tmp_path / "arc", today=date(2026, 4, 22))
    assert plan.header == []
    assert plan.rows_to_keep == []


def test_plan_archive_rejects_unknown_file(tmp_path: Path) -> None:
    source = tmp_path / "habits.csv"
    source.write_text("habit_id\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not an archivable file"):
        plan_archive(source, archive_dir=tmp_path / "arc", today=date(2026, 4, 22))


def test_plan_archive_rejects_negative_min_age(tmp_path: Path) -> None:
    source = tmp_path / "tasks.csv"
    _write_csv(source, TASKS_HEADER, [])
    with pytest.raises(ValueError, match="min_age_days must be >= 0"):
        plan_archive(
            source,
            archive_dir=tmp_path / "arc",
            today=date(2026, 4, 22),
            min_age_days=-1,
        )


def test_plan_archive_rejects_file_missing_status_column(tmp_path: Path) -> None:
    source = tmp_path / "tasks.csv"
    bad_header = [h for h in TASKS_HEADER if h != "status"]
    source.write_text(",".join(bad_header) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing 'status' column"):
        plan_archive(source, archive_dir=tmp_path / "arc", today=date(2026, 4, 22))


def test_plan_archive_rejects_file_missing_age_column(tmp_path: Path) -> None:
    source = tmp_path / "tasks.csv"
    bad_header = [h for h in TASKS_HEADER if h != "last_updated"]
    source.write_text(",".join(bad_header) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing 'last_updated' column"):
        plan_archive(source, archive_dir=tmp_path / "arc", today=date(2026, 4, 22))


def test_plan_archive_rejects_row_with_wrong_column_count(tmp_path: Path) -> None:
    source = tmp_path / "tasks.csv"
    source.write_text(
        ",".join(TASKS_HEADER) + "\n" + "only,two\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="expected"):
        plan_archive(source, archive_dir=tmp_path / "arc", today=date(2026, 4, 22))


# ---------------------------------------------------------------------------
# plan_archive: per-file semantics (goals, projects, time_blocks)
# ---------------------------------------------------------------------------


def test_plan_archive_goals_uses_last_updated(tmp_path: Path) -> None:
    source = tmp_path / "goals.csv"
    _write_csv(
        source,
        GOALS_HEADER,
        [
            {
                "goal_id": "g1",
                "area": "work",
                "title": "Done goal",
                "horizon": "quarter",
                "target_date": "2025-01-01",
                "metric_name": "",
                "metric_target": "",
                "metric_current": "",
                "status": "completed",
                "last_updated": "2025-01-15",
                "notes": "",
            },
            {
                "goal_id": "g2",
                "area": "work",
                "title": "Active goal",
                "horizon": "quarter",
                "target_date": "2026-06-01",
                "metric_name": "",
                "metric_target": "",
                "metric_current": "",
                "status": "active",
                "last_updated": "2025-01-15",
                "notes": "",
            },
        ],
    )
    plan = plan_archive(source, archive_dir=tmp_path / "arc", today=date(2026, 4, 22))
    # 'completed' goal is terminal and old; 'active' goal is kept regardless of age.
    assert plan.archive_count == 1
    assert plan.keep_count == 1
    assert plan.buckets["2025"][0]["goal_id"] == "g1"


def test_plan_archive_projects_only_completed_is_terminal(tmp_path: Path) -> None:
    source = tmp_path / "projects.csv"
    _write_csv(
        source,
        PROJECTS_HEADER,
        [
            {
                "project_id": "p_done",
                "area": "x",
                "name": "Shipped",
                "status": "completed",
                "start_date": "2024-01-01",
                "target_date": "2024-06-01",
                "description": "",
                "last_updated": "2024-07-01",
                "notes": "",
                "active": "false",
            },
            {
                "project_id": "p_paused",
                "area": "x",
                "name": "Paused — not terminal",
                "status": "paused",
                "start_date": "2024-01-01",
                "target_date": "",
                "description": "",
                "last_updated": "2024-07-01",
                "notes": "",
                "active": "false",
            },
        ],
    )
    plan = plan_archive(source, archive_dir=tmp_path / "arc", today=date(2026, 4, 22))
    archived = {r["project_id"] for rows in plan.buckets.values() for r in rows}
    assert archived == {"p_done"}


def test_plan_archive_time_blocks_uses_date_field(tmp_path: Path) -> None:
    source = tmp_path / "time_blocks.csv"
    _write_csv(
        source,
        TIME_BLOCKS_HEADER,
        [
            {
                "block_id": "b1",
                "date": "2024-01-15",
                "start": "09:00",
                "end": "10:00",
                "title": "Old completed block",
                "domain": "",
                "task_id": "",
                "source": "manual",
                "status": "completed",
                "notes": "",
            },
            {
                "block_id": "b2",
                "date": "2024-01-15",
                "start": "10:00",
                "end": "11:00",
                "title": "Old skipped block",
                "domain": "",
                "task_id": "",
                "source": "manual",
                "status": "skipped",
                "notes": "",
            },
            {
                "block_id": "b3",
                "date": "2026-04-20",
                "start": "10:00",
                "end": "11:00",
                "title": "Fresh completed block",
                "domain": "",
                "task_id": "",
                "source": "manual",
                "status": "completed",
                "notes": "",
            },
        ],
    )
    plan = plan_archive(source, archive_dir=tmp_path / "arc", today=date(2026, 4, 22))
    assert plan.archive_count == 2
    assert plan.keep_count == 1
    assert "2024" in plan.buckets


# ---------------------------------------------------------------------------
# ArchivePlan properties
# ---------------------------------------------------------------------------


def test_archive_plan_archive_path_composition(tmp_path: Path) -> None:
    plan = ArchivePlan(
        source=tmp_path / "tasks.csv",
        archive_dir=tmp_path / "arc",
        header=TASKS_HEADER,
        rows_to_keep=[],
        buckets={"2024": [], "undated": []},
    )
    assert plan.archive_path("2024") == tmp_path / "arc" / "tasks-2024.csv"
    assert plan.archive_path("undated") == tmp_path / "arc" / "tasks-undated.csv"


# ---------------------------------------------------------------------------
# apply_plan: filesystem effects
# ---------------------------------------------------------------------------


def test_apply_plan_writes_new_archive_and_truncates_source(tmp_path: Path) -> None:
    source = tmp_path / "tasks.csv"
    arc = tmp_path / "arc"
    _write_csv(
        source,
        TASKS_HEADER,
        [
            _task_row("keep", "in_progress", "2026-04-10"),
            _task_row("archive_me", "done", "2024-06-01"),
        ],
    )
    plan = plan_archive(source, archive_dir=arc, today=date(2026, 4, 22))
    apply_plan(plan)

    # Source retains exactly the "keep" row, headers intact
    header, rows = _read_csv_rows(source)
    assert header == TASKS_HEADER
    assert [r["task_id"] for r in rows] == ["keep"]

    # Archive bucket has the one archived row
    archive_path = arc / "tasks-2024.csv"
    assert archive_path.exists()
    arc_header, arc_rows = _read_csv_rows(archive_path)
    assert arc_header == TASKS_HEADER
    assert [r["task_id"] for r in arc_rows] == ["archive_me"]


def test_apply_plan_appends_to_existing_archive(tmp_path: Path) -> None:
    source = tmp_path / "tasks.csv"
    arc = tmp_path / "arc"
    arc.mkdir()
    # Pre-existing archive with one row
    _write_csv(
        arc / "tasks-2024.csv",
        TASKS_HEADER,
        [_task_row("prev_archived", "done", "2024-03-01")],
    )
    _write_csv(
        source,
        TASKS_HEADER,
        [_task_row("newly_archived", "done", "2024-09-01")],
    )
    plan = plan_archive(source, archive_dir=arc, today=date(2026, 4, 22))
    apply_plan(plan)

    _, rows = _read_csv_rows(arc / "tasks-2024.csv")
    ids = [r["task_id"] for r in rows]
    assert ids == ["prev_archived", "newly_archived"]

    _, src_rows = _read_csv_rows(source)
    assert src_rows == []


def test_apply_plan_refuses_header_drift_in_existing_archive(
    tmp_path: Path,
) -> None:
    source = tmp_path / "tasks.csv"
    arc = tmp_path / "arc"
    arc.mkdir()
    # Archive has an older, different header
    drifted = TASKS_HEADER[:-1]
    _write_csv(
        arc / "tasks-2024.csv",
        drifted,
        [dict.fromkeys(drifted, "x")],
    )
    _write_csv(
        source,
        TASKS_HEADER,
        [_task_row("t", "done", "2024-01-01")],
    )
    plan = plan_archive(source, archive_dir=arc, today=date(2026, 4, 22))
    with pytest.raises(ValueError, match="header mismatch"):
        apply_plan(plan)

    # Source MUST NOT have been touched — header mismatch aborts before rewrite.
    _, src_rows = _read_csv_rows(source)
    assert len(src_rows) == 1


def test_apply_plan_noop_when_nothing_to_archive(tmp_path: Path) -> None:
    source = tmp_path / "tasks.csv"
    arc = tmp_path / "arc"
    _write_csv(
        source,
        TASKS_HEADER,
        [_task_row("active", "queued", "2026-04-01")],
    )
    pre_mtime = source.stat().st_mtime_ns
    plan = plan_archive(source, archive_dir=arc, today=date(2026, 4, 22))
    apply_plan(plan)
    # Nothing archived → source file untouched, archive dir not created
    assert source.stat().st_mtime_ns == pre_mtime
    assert not arc.exists()


def test_apply_plan_noop_for_empty_source(tmp_path: Path) -> None:
    source = tmp_path / "tasks.csv"
    arc = tmp_path / "arc"
    # Missing source → empty plan → apply is a no-op and does not crash.
    plan = plan_archive(source, archive_dir=arc, today=date(2026, 4, 22))
    apply_plan(plan)
    assert not source.exists()
    assert not arc.exists()


def test_apply_plan_noop_when_header_missing_despite_buckets(
    tmp_path: Path,
) -> None:
    # Defensive guard: a hand-constructed plan with rows but no header must
    # not attempt to write (real plans from plan_archive never reach this
    # state, but apply_plan is a public entry-point and should be safe).
    plan = ArchivePlan(
        source=tmp_path / "tasks.csv",
        archive_dir=tmp_path / "arc",
        header=[],
        rows_to_keep=[],
        buckets={"2024": [{"task_id": "x"}]},
    )
    apply_plan(plan)
    assert not (tmp_path / "arc").exists()


def test_apply_plan_splits_across_year_buckets(tmp_path: Path) -> None:
    source = tmp_path / "tasks.csv"
    arc = tmp_path / "arc"
    _write_csv(
        source,
        TASKS_HEADER,
        [
            _task_row("t2023", "done", "2023-05-01"),
            _task_row("t2024", "done", "2024-05-01"),
            _task_row("t2025_a", "done", "2025-01-15"),
            _task_row("t2025_b", "dropped", "2025-07-20"),
        ],
    )
    plan = plan_archive(source, archive_dir=arc, today=date(2026, 4, 22))
    apply_plan(plan)

    assert {p.name for p in arc.iterdir()} == {
        "tasks-2023.csv",
        "tasks-2024.csv",
        "tasks-2025.csv",
    }
    _, rows_2025 = _read_csv_rows(arc / "tasks-2025.csv")
    assert {r["task_id"] for r in rows_2025} == {"t2025_a", "t2025_b"}


def test_apply_plan_atomic_no_stray_tempfiles(tmp_path: Path) -> None:
    source = tmp_path / "tasks.csv"
    arc = tmp_path / "arc"
    _write_csv(
        source,
        TASKS_HEADER,
        [_task_row("t", "done", "2024-01-01")],
    )
    plan = plan_archive(source, archive_dir=arc, today=date(2026, 4, 22))
    apply_plan(plan)
    # Verify no leaked .tmp files
    leftovers = [p.name for p in tmp_path.rglob(".tasks.csv.*.tmp")]
    assert leftovers == []


def test_apply_plan_atomic_write_cleans_tmp_on_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "tasks.csv"
    arc = tmp_path / "arc"
    _write_csv(
        source,
        TASKS_HEADER,
        [_task_row("t", "done", "2024-01-01")],
    )
    plan = plan_archive(source, archive_dir=arc, today=date(2026, 4, 22))

    # Force os.replace to fail, simulating a mid-write crash.
    real_replace = archive_completed.os.replace

    def boom(src: str, dst: str) -> None:
        # Let the bucket write succeed, then fail on the canonical rewrite.
        if str(dst).endswith("tasks.csv"):
            raise RuntimeError("simulated failure")
        real_replace(src, dst)

    monkeypatch.setattr(archive_completed.os, "replace", boom)
    with pytest.raises(RuntimeError):
        apply_plan(plan)

    # Tempfile for the canonical rewrite must be cleaned up despite the crash.
    leftovers = list(tmp_path.rglob(".tasks.csv.*.tmp"))
    assert leftovers == []


# ---------------------------------------------------------------------------
# archive_file / archive_all wrappers
# ---------------------------------------------------------------------------


def test_archive_file_dry_run_does_not_write(tmp_path: Path) -> None:
    source = tmp_path / "tasks.csv"
    arc = tmp_path / "arc"
    _write_csv(
        source,
        TASKS_HEADER,
        [_task_row("old", "done", "2024-01-01")],
    )
    before = source.read_bytes()
    plan = archive_file(source, arc, today=date(2026, 4, 22), dry_run=True)
    assert plan.archive_count == 1
    assert source.read_bytes() == before
    assert not arc.exists()


def test_archive_file_writes_when_not_dry_run(tmp_path: Path) -> None:
    source = tmp_path / "tasks.csv"
    arc = tmp_path / "arc"
    _write_csv(
        source,
        TASKS_HEADER,
        [_task_row("old", "done", "2024-01-01")],
    )
    plan = archive_file(source, arc, today=date(2026, 4, 22))
    assert plan.archive_count == 1
    assert (arc / "tasks-2024.csv").exists()
    _, rows = _read_csv_rows(source)
    assert rows == []


def test_archive_file_uses_today_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "tasks.csv"
    arc = tmp_path / "arc"
    _write_csv(
        source,
        TASKS_HEADER,
        [_task_row("old", "done", "2020-01-01")],
    )

    class _FrozenDate(date):
        @classmethod
        def today(cls) -> date:
            return date(2026, 4, 22)

    monkeypatch.setattr(archive_completed, "date", _FrozenDate)
    plan = archive_file(source, arc)
    assert plan.archive_count == 1


def test_archive_all_visits_only_supported_files(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical"
    arc = tmp_path / "arc"
    canonical.mkdir()
    # Supported files
    _write_csv(
        canonical / "tasks.csv",
        TASKS_HEADER,
        [_task_row("t", "done", "2024-01-01")],
    )
    _write_csv(
        canonical / "goals.csv",
        GOALS_HEADER,
        [],
    )
    # Unsupported file: habits has no status column in the archive sense
    (canonical / "habits.csv").write_text("habit_id\n", encoding="utf-8")

    plans = archive_all(canonical, arc, today=date(2026, 4, 22))
    assert set(plans.keys()) == {"tasks.csv", "goals.csv"}
    assert plans["tasks.csv"].archive_count == 1
    assert plans["goals.csv"].archive_count == 0


def test_archive_all_skips_missing_files(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical"
    canonical.mkdir()
    _write_csv(
        canonical / "tasks.csv",
        TASKS_HEADER,
        [_task_row("t", "done", "2024-01-01")],
    )
    plans = archive_all(canonical, tmp_path / "arc", today=date(2026, 4, 22))
    assert set(plans.keys()) == {"tasks.csv"}


def test_archive_all_dry_run_does_not_write(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical"
    canonical.mkdir()
    _write_csv(
        canonical / "tasks.csv",
        TASKS_HEADER,
        [_task_row("t", "done", "2024-01-01")],
    )
    plans = archive_all(
        canonical, tmp_path / "arc", today=date(2026, 4, 22), dry_run=True
    )
    assert plans["tasks.csv"].archive_count == 1
    # tasks.csv untouched; archive dir not created
    _, rows = _read_csv_rows(canonical / "tasks.csv")
    assert len(rows) == 1
    assert not (tmp_path / "arc").exists()


def test_archive_all_uses_default_today(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canonical = tmp_path / "canonical"
    canonical.mkdir()
    _write_csv(
        canonical / "tasks.csv",
        TASKS_HEADER,
        [_task_row("t", "done", "2020-01-01")],
    )

    class _FrozenDate(date):
        @classmethod
        def today(cls) -> date:
            return date(2026, 4, 22)

    monkeypatch.setattr(archive_completed, "date", _FrozenDate)
    plans = archive_all(canonical, tmp_path / "arc")
    assert plans["tasks.csv"].archive_count == 1


# ---------------------------------------------------------------------------
# format_plan rendering
# ---------------------------------------------------------------------------


def test_format_plan_summary(tmp_path: Path) -> None:
    source = tmp_path / "tasks.csv"
    arc = tmp_path / "arc"
    _write_csv(
        source,
        TASKS_HEADER,
        [
            _task_row("a", "done", "2024-01-01"),
            _task_row("b", "in_progress", "2026-04-01"),
        ],
    )
    plan = plan_archive(source, archive_dir=arc, today=date(2026, 4, 22))
    report = format_plan(plan)
    assert "tasks.csv: archive 1, keep 1" in report
    assert "tasks-2024.csv" in report


def test_format_plan_empty_buckets(tmp_path: Path) -> None:
    source = tmp_path / "tasks.csv"
    arc = tmp_path / "arc"
    _write_csv(source, TASKS_HEADER, [])
    plan = plan_archive(source, archive_dir=arc, today=date(2026, 4, 22))
    report = format_plan(plan)
    # No bucket lines when there's nothing to archive.
    assert report == "tasks.csv: archive 0, keep 0"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_file_dry_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    canonical = tmp_path / "canonical"
    arc = tmp_path / "arc"
    canonical.mkdir()
    _write_csv(
        canonical / "tasks.csv",
        TASKS_HEADER,
        [_task_row("old", "done", "2024-01-01")],
    )
    rc = main(
        [
            "--file",
            "tasks.csv",
            "--canonical-dir",
            str(canonical),
            "--archive-dir",
            str(arc),
            "--today",
            "2026-04-22",
            "--dry-run",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out
    assert "1 row(s) archived" in out
    # Dry run: canonical and archive untouched
    _, rows = _read_csv_rows(canonical / "tasks.csv")
    assert len(rows) == 1
    assert not arc.exists()


def test_cli_all_writes_archive(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    canonical = tmp_path / "canonical"
    arc = tmp_path / "arc"
    canonical.mkdir()
    _write_csv(
        canonical / "tasks.csv",
        TASKS_HEADER,
        [_task_row("old", "done", "2024-01-01")],
    )
    _write_csv(
        canonical / "goals.csv",
        GOALS_HEADER,
        [],
    )
    rc = main(
        [
            "--all",
            "--canonical-dir",
            str(canonical),
            "--archive-dir",
            str(arc),
            "--today",
            "2026-04-22",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "DRY RUN" not in out
    assert "1 row(s) archived" in out
    assert (arc / "tasks-2024.csv").exists()


def test_cli_requires_file_or_all(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main(["--canonical-dir", str(tmp_path)])


def test_cli_archive_undated_flag(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical"
    arc = tmp_path / "arc"
    canonical.mkdir()
    _write_csv(
        canonical / "tasks.csv",
        TASKS_HEADER,
        [_task_row("nodate", "done", "")],
    )
    rc = main(
        [
            "--file",
            "tasks.csv",
            "--canonical-dir",
            str(canonical),
            "--archive-dir",
            str(arc),
            "--today",
            "2026-04-22",
            "--archive-undated",
        ]
    )
    assert rc == 0
    assert (arc / "tasks-undated.csv").exists()
