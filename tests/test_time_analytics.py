"""Unit tests for ``time_analytics.py``."""

from __future__ import annotations

import sys
from datetime import date, time
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "01-ops" / "life-os" / "scripts" / "time_analytics.py"
MODULE_NAME = "life_os_time_analytics"

SPEC = spec_from_file_location(MODULE_NAME, MODULE_PATH)
time_analytics = module_from_spec(SPEC)
assert SPEC.loader is not None
# Register before exec_module — dataclasses resolve their module via sys.modules.
sys.modules[MODULE_NAME] = time_analytics
SPEC.loader.exec_module(time_analytics)

TimeLog = time_analytics.TimeLog
TimeBlock = time_analytics.TimeBlock


LOG_HEADER = (
    "log_id,date,activity,domain,duration_mins,start_time,end_time,notes,last_updated"
)
BLOCK_HEADER = "block_id,date,start,end,title,domain,task_id,source,status,notes"


def _write_logs(path: Path, rows: list[str]) -> None:
    path.write_text("\n".join([LOG_HEADER, *rows]) + "\n", encoding="utf-8")


def _write_blocks(path: Path, rows: list[str]) -> None:
    path.write_text("\n".join([BLOCK_HEADER, *rows]) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# _parse_int / _parse_time / _parse_date / _domain_of / _duration_between
# ---------------------------------------------------------------------------


class TestLowLevelParsers:
    def test_parse_int_accepts_valid_positive(self) -> None:
        assert time_analytics._parse_int("42") == 42

    def test_parse_int_rejects_zero_and_negative(self) -> None:
        assert time_analytics._parse_int("0") is None
        assert time_analytics._parse_int("-5") is None

    def test_parse_int_rejects_blank_and_garbage(self) -> None:
        assert time_analytics._parse_int("") is None
        assert time_analytics._parse_int("   ") is None
        assert time_analytics._parse_int("abc") is None

    def test_parse_time_accepts_hm_and_hms(self) -> None:
        assert time_analytics._parse_time("09:30") == time(9, 30)
        assert time_analytics._parse_time("09:30:45") == time(9, 30, 45)

    def test_parse_time_rejects_blank_and_garbage(self) -> None:
        assert time_analytics._parse_time("") is None
        assert time_analytics._parse_time("25:00") is None
        assert time_analytics._parse_time("nope") is None

    def test_parse_date_accepts_iso(self) -> None:
        assert time_analytics._parse_date("2026-04-22") == date(2026, 4, 22)

    def test_parse_date_rejects_blank_and_garbage(self) -> None:
        assert time_analytics._parse_date("") is None
        assert time_analytics._parse_date("04/22/2026") is None

    def test_domain_of_normalizes_blank_to_unassigned(self) -> None:
        assert time_analytics._domain_of(None) == "unassigned"
        assert time_analytics._domain_of("") == "unassigned"
        assert time_analytics._domain_of("   ") == "unassigned"

    def test_domain_of_preserves_case(self) -> None:
        # Domains are user-authored labels; don't lowercase them.
        assert time_analytics._domain_of("Work") == "Work"
        assert time_analytics._domain_of("  health  ") == "health"

    def test_duration_between_whole_minutes(self) -> None:
        assert time_analytics._duration_between(time(9, 0), time(10, 30)) == 90

    def test_duration_between_clamps_negative_to_zero(self) -> None:
        assert time_analytics._duration_between(time(11, 0), time(9, 0)) == 0

    def test_duration_between_equal_times_is_zero(self) -> None:
        assert time_analytics._duration_between(time(9, 0), time(9, 0)) == 0


# ---------------------------------------------------------------------------
# load_time_logs
# ---------------------------------------------------------------------------


class TestLoadTimeLogs:
    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        assert time_analytics.load_time_logs(tmp_path / "nope.csv") == []

    def test_loads_well_formed_row(self, tmp_path: Path) -> None:
        path = tmp_path / "logs.csv"
        _write_logs(path, ["l1,2026-04-22,Deep work,work,90,09:00,10:30,,2026-04-22"])
        logs = time_analytics.load_time_logs(path)
        assert logs == [
            TimeLog(
                entry_date=date(2026, 4, 22),
                activity="Deep work",
                domain="work",
                duration_mins=90,
            )
        ]

    def test_computes_duration_from_start_end_when_duration_blank(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "logs.csv"
        _write_logs(path, ["l1,2026-04-22,Standup,work,,09:00,09:15,,2026-04-22"])
        logs = time_analytics.load_time_logs(path)
        assert len(logs) == 1
        assert logs[0].duration_mins == 15

    def test_skips_row_when_duration_and_times_both_missing(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "logs.csv"
        _write_logs(path, ["l1,2026-04-22,Vague entry,work,,,,,2026-04-22"])
        assert time_analytics.load_time_logs(path) == []

    def test_skips_row_when_span_is_zero(self, tmp_path: Path) -> None:
        path = tmp_path / "logs.csv"
        # start == end → 0 minutes → drop row
        _write_logs(path, ["l1,2026-04-22,Noop,work,,09:00,09:00,,2026-04-22"])
        assert time_analytics.load_time_logs(path) == []

    def test_skips_row_missing_date(self, tmp_path: Path) -> None:
        path = tmp_path / "logs.csv"
        _write_logs(path, ["l1,,Activity,work,30,,,note,2026-04-22"])
        assert time_analytics.load_time_logs(path) == []

    def test_skips_row_missing_activity(self, tmp_path: Path) -> None:
        path = tmp_path / "logs.csv"
        _write_logs(path, ["l1,2026-04-22,,work,30,,,,"])
        assert time_analytics.load_time_logs(path) == []

    def test_skips_row_with_bad_date(self, tmp_path: Path) -> None:
        path = tmp_path / "logs.csv"
        _write_logs(path, ["l1,not-a-date,Activity,work,30,,,,"])
        assert time_analytics.load_time_logs(path) == []

    def test_blank_domain_buckets_to_unassigned(self, tmp_path: Path) -> None:
        path = tmp_path / "logs.csv"
        _write_logs(path, ["l1,2026-04-22,Reading,,20,,,,"])
        logs = time_analytics.load_time_logs(path)
        assert len(logs) == 1
        assert logs[0].domain == "unassigned"

    def test_ignores_negative_duration(self, tmp_path: Path) -> None:
        path = tmp_path / "logs.csv"
        _write_logs(path, ["l1,2026-04-22,Activity,work,-30,,,,"])
        assert time_analytics.load_time_logs(path) == []


# ---------------------------------------------------------------------------
# load_time_blocks
# ---------------------------------------------------------------------------


class TestLoadTimeBlocks:
    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        assert time_analytics.load_time_blocks(tmp_path / "nope.csv") == []

    def test_loads_well_formed_row(self, tmp_path: Path) -> None:
        path = tmp_path / "blocks.csv"
        _write_blocks(
            path, ["b1,2026-04-22,09:00,10:30,Deep work,work,,manual,planned,"]
        )
        blocks = time_analytics.load_time_blocks(path)
        assert blocks == [
            TimeBlock(
                entry_date=date(2026, 4, 22),
                start=time(9, 0),
                end=time(10, 30),
                title="Deep work",
                domain="work",
                status="planned",
                duration_mins=90,
            )
        ]

    def test_skips_zero_duration_block(self, tmp_path: Path) -> None:
        path = tmp_path / "blocks.csv"
        _write_blocks(path, ["b1,2026-04-22,09:00,09:00,Noop,work,,manual,planned,"])
        assert time_analytics.load_time_blocks(path) == []

    def test_skips_block_missing_date_start_or_end(self, tmp_path: Path) -> None:
        path = tmp_path / "blocks.csv"
        _write_blocks(
            path,
            [
                "b1,,09:00,10:00,A,work,,manual,planned,",
                "b2,2026-04-22,,10:00,A,work,,manual,planned,",
                "b3,2026-04-22,09:00,,A,work,,manual,planned,",
            ],
        )
        assert time_analytics.load_time_blocks(path) == []

    def test_blank_domain_buckets_to_unassigned(self, tmp_path: Path) -> None:
        path = tmp_path / "blocks.csv"
        _write_blocks(path, ["b1,2026-04-22,09:00,10:00,Read,,,,,"])
        blocks = time_analytics.load_time_blocks(path)
        assert len(blocks) == 1
        assert blocks[0].domain == "unassigned"

    def test_status_lowercased(self, tmp_path: Path) -> None:
        path = tmp_path / "blocks.csv"
        _write_blocks(path, ["b1,2026-04-22,09:00,10:00,Read,work,,manual,COMPLETED,"])
        blocks = time_analytics.load_time_blocks(path)
        assert blocks[0].status == "completed"


# ---------------------------------------------------------------------------
# compute_domain_stats
# ---------------------------------------------------------------------------


class TestComputeDomainStats:
    def test_today_week_month_totals(self) -> None:
        today = date(2026, 4, 22)  # Wednesday
        logs = [
            TimeLog(today, "Deep work", "work", 60),  # today & this week
            TimeLog(date(2026, 4, 20), "Meetings", "work", 30),  # Mon — this week
            TimeLog(date(2026, 4, 10), "Old work", "work", 120),  # within 30d
            TimeLog(date(2026, 3, 1), "Ancient", "work", 999),  # outside 30d
        ]
        stats = time_analytics.compute_domain_stats("work", logs, [], today)
        assert stats.today_mins == 60
        assert stats.week_mins == 90
        assert stats.month_mins == 210
        assert stats.total_mins == 1209

    def test_unique_activities_and_top_activity(self) -> None:
        today = date(2026, 4, 22)
        logs = [
            TimeLog(today, "Coding", "work", 30),
            TimeLog(today, "Coding", "work", 30),
            TimeLog(today, "Email", "work", 20),
            TimeLog(today, "Reading", "health", 15),
        ]
        stats = time_analytics.compute_domain_stats("work", logs, [], today)
        assert stats.unique_activities == 2
        assert stats.top_activity == "Coding"
        assert stats.top_activity_mins == 60

    def test_top_activity_ties_break_alphabetically(self) -> None:
        today = date(2026, 4, 22)
        logs = [
            TimeLog(today, "Zeta", "work", 30),
            TimeLog(today, "Alpha", "work", 30),
        ]
        stats = time_analytics.compute_domain_stats("work", logs, [], today)
        # Same minutes; "Alpha" wins alphabetically for deterministic reports.
        assert stats.top_activity == "Alpha"

    def test_empty_domain_returns_zeros_and_none_top(self) -> None:
        stats = time_analytics.compute_domain_stats(
            "missing", [], [], date(2026, 4, 22)
        )
        assert stats.today_mins == 0
        assert stats.week_mins == 0
        assert stats.month_mins == 0
        assert stats.unique_activities == 0
        assert stats.top_activity is None
        assert stats.top_activity_mins == 0
        assert stats.planned_week_mins == 0
        assert stats.week_adherence is None

    def test_planned_week_sums_blocks_in_current_week_only(self) -> None:
        today = date(2026, 4, 22)  # Wednesday
        blocks = [
            TimeBlock(
                date(2026, 4, 20), time(9), time(10), "Mon", "work", "planned", 60
            ),
            TimeBlock(
                date(2026, 4, 26), time(9), time(11), "Sun", "work", "planned", 120
            ),
            TimeBlock(
                date(2026, 4, 13), time(9), time(10), "PrevWk", "work", "planned", 60
            ),
            TimeBlock(
                date(2026, 4, 22), time(14), time(15), "Today", "health", "planned", 60
            ),
        ]
        stats = time_analytics.compute_domain_stats("work", [], blocks, today)
        # Mon + Sun blocks (both in ISO week anchored at Mon 2026-04-20).
        assert stats.planned_week_mins == 180
        # No logs, so adherence against 180 planned is 0.0.
        assert stats.week_adherence == 0.0

    def test_adherence_none_when_nothing_planned(self) -> None:
        today = date(2026, 4, 22)
        logs = [TimeLog(today, "Work", "work", 60)]
        stats = time_analytics.compute_domain_stats("work", logs, [], today)
        assert stats.planned_week_mins == 0
        assert stats.week_adherence is None

    def test_adherence_can_exceed_one_when_overlogged(self) -> None:
        today = date(2026, 4, 22)
        logs = [TimeLog(today, "Work", "work", 180)]  # logged 3h
        blocks = [TimeBlock(today, time(9), time(10), "Planned", "work", "planned", 60)]
        stats = time_analytics.compute_domain_stats("work", logs, blocks, today)
        assert stats.planned_week_mins == 60
        assert stats.week_adherence == pytest.approx(3.0)

    def test_week_start_is_monday(self) -> None:
        # Sunday 2026-04-26 → week spans Mon 2026-04-20..Sun 2026-04-26.
        today = date(2026, 4, 26)
        logs = [
            TimeLog(date(2026, 4, 20), "Start of week", "work", 60),
            TimeLog(date(2026, 4, 26), "End of week", "work", 30),
            TimeLog(date(2026, 4, 19), "Previous week Sunday", "work", 45),
        ]
        stats = time_analytics.compute_domain_stats("work", logs, [], today)
        assert stats.week_mins == 90

    def test_month_window_is_30_days_inclusive(self) -> None:
        today = date(2026, 4, 22)
        logs = [
            TimeLog(date(2026, 3, 24), "Boundary in", "work", 30),  # day -29
            TimeLog(date(2026, 3, 23), "Boundary out", "work", 60),  # day -30 → out
        ]
        stats = time_analytics.compute_domain_stats("work", logs, [], today)
        assert stats.month_mins == 30

    def test_other_domains_not_mixed_in(self) -> None:
        today = date(2026, 4, 22)
        logs = [
            TimeLog(today, "A", "work", 30),
            TimeLog(today, "B", "health", 45),
        ]
        stats = time_analytics.compute_domain_stats("work", logs, [], today)
        assert stats.month_mins == 30
        assert stats.unique_activities == 1


# ---------------------------------------------------------------------------
# analyze — integration over logs + blocks
# ---------------------------------------------------------------------------


class TestAnalyze:
    def test_reads_csvs_and_sorts_by_month_desc(self, tmp_path: Path) -> None:
        logs_path = tmp_path / "logs.csv"
        blocks_path = tmp_path / "blocks.csv"
        _write_logs(
            logs_path,
            [
                "l1,2026-04-22,Coding,work,60,,,,2026-04-22",
                "l2,2026-04-20,Coding,work,120,,,,2026-04-20",
                "l3,2026-04-22,Running,health,30,,,,2026-04-22",
            ],
        )
        _write_blocks(
            blocks_path,
            [
                "b1,2026-04-22,09:00,11:00,Deep work,work,,manual,planned,",
                "b2,2026-04-22,18:00,19:00,Run,health,,manual,planned,",
            ],
        )

        report = time_analytics.analyze(
            logs_path=logs_path, blocks_path=blocks_path, today=date(2026, 4, 22)
        )

        assert report.anchor == date(2026, 4, 22)
        assert [s.domain for s in report.domain_stats] == ["work", "health"]
        assert report.total_today_mins == 90
        assert report.total_week_mins == 210
        assert report.total_month_mins == 210
        assert report.active_days_last_30 == 2

    def test_includes_planned_only_domains(self, tmp_path: Path) -> None:
        logs_path = tmp_path / "logs.csv"
        blocks_path = tmp_path / "blocks.csv"
        _write_logs(logs_path, [])
        _write_blocks(
            blocks_path,
            ["b1,2026-04-22,09:00,10:00,Yoga,health,,manual,planned,"],
        )

        report = time_analytics.analyze(
            logs_path=logs_path, blocks_path=blocks_path, today=date(2026, 4, 22)
        )

        assert [s.domain for s in report.domain_stats] == ["health"]
        assert report.domain_stats[0].planned_week_mins == 60
        assert report.domain_stats[0].week_mins == 0
        assert report.domain_stats[0].week_adherence == 0.0

    def test_missing_inputs_yield_empty_report(self, tmp_path: Path) -> None:
        report = time_analytics.analyze(
            logs_path=tmp_path / "absent_logs.csv",
            blocks_path=tmp_path / "absent_blocks.csv",
            today=date(2026, 4, 22),
        )
        assert report.domain_stats == []
        assert report.total_today_mins == 0
        assert report.total_week_mins == 0
        assert report.total_month_mins == 0
        assert report.active_days_last_30 == 0

    def test_default_today_uses_date_today(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class FrozenDate(date):
            @classmethod
            def today(cls) -> FrozenDate:  # type: ignore[override]
                return cls(2026, 4, 22)

        monkeypatch.setattr(time_analytics, "date", FrozenDate)
        logs_path = tmp_path / "logs.csv"
        blocks_path = tmp_path / "blocks.csv"
        _write_logs(logs_path, ["l1,2026-04-22,X,work,30,,,,"])
        _write_blocks(blocks_path, [])
        report = time_analytics.analyze(logs_path=logs_path, blocks_path=blocks_path)
        assert report.anchor == date(2026, 4, 22)


# ---------------------------------------------------------------------------
# format_duration / format_report
# ---------------------------------------------------------------------------


class TestFormatting:
    @pytest.mark.parametrize(
        ("mins", "expected"),
        [
            (0, "-"),
            (-10, "-"),
            (5, "5m"),
            (59, "59m"),
            (60, "1h"),
            (90, "1h 30m"),
            (125, "2h 5m"),
        ],
    )
    def test_format_duration(self, mins: int, expected: str) -> None:
        assert time_analytics.format_duration(mins) == expected

    def test_format_report_handles_empty_report(self) -> None:
        empty = time_analytics.TimeReport(
            anchor=date(2026, 4, 22),
            domain_stats=[],
            total_today_mins=0,
            total_week_mins=0,
            total_month_mins=0,
            active_days_last_30=0,
        )
        assert time_analytics.format_report(empty) == "No time logs or blocks found.\n"

    def test_format_report_renders_rows_and_totals(self, tmp_path: Path) -> None:
        logs_path = tmp_path / "logs.csv"
        blocks_path = tmp_path / "blocks.csv"
        _write_logs(
            logs_path,
            [
                "l1,2026-04-22,Coding,work,60,,,,2026-04-22",
                "l2,2026-04-22,Running,health,30,,,,2026-04-22",
            ],
        )
        _write_blocks(
            blocks_path,
            ["b1,2026-04-22,09:00,10:00,Focus,work,,manual,planned,"],
        )
        report = time_analytics.analyze(
            logs_path=logs_path, blocks_path=blocks_path, today=date(2026, 4, 22)
        )
        rendered = time_analytics.format_report(report)
        assert "work" in rendered
        assert "health" in rendered
        assert "Coding" in rendered
        assert "Running" in rendered
        assert "TOTAL" in rendered
        assert "Active days in last 30:" in rendered
        assert "100%" in rendered  # 60 logged / 60 planned for work

    def test_format_report_shows_dash_when_no_plan(self, tmp_path: Path) -> None:
        logs_path = tmp_path / "logs.csv"
        blocks_path = tmp_path / "blocks.csv"
        _write_logs(logs_path, ["l1,2026-04-22,A,work,30,,,,"])
        _write_blocks(blocks_path, [])
        report = time_analytics.analyze(
            logs_path=logs_path, blocks_path=blocks_path, today=date(2026, 4, 22)
        )
        rendered = time_analytics.format_report(report)
        # Adherence column for unplanned domain should display as "-".
        header_split = rendered.splitlines()
        # Find row starting with domain "work"
        domain_row = next(ln for ln in header_split if ln.startswith("work"))
        # The last-but-one field is adherence — easier to check: no "%" for this domain.
        assert "%" not in domain_row


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


class TestMain:
    def test_main_runs_against_custom_paths(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        logs_path = tmp_path / "logs.csv"
        blocks_path = tmp_path / "blocks.csv"
        _write_logs(logs_path, ["l1,2026-04-22,Coding,work,60,,,,2026-04-22"])
        _write_blocks(blocks_path, [])
        rc = time_analytics.main(
            [
                "--logs",
                str(logs_path),
                "--blocks",
                str(blocks_path),
                "--today",
                "2026-04-22",
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "Coding" in out
        assert "work" in out

    def test_main_handles_missing_files(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc = time_analytics.main(
            [
                "--logs",
                str(tmp_path / "absent.csv"),
                "--blocks",
                str(tmp_path / "absent.csv"),
                "--today",
                "2026-04-22",
            ]
        )
        assert rc == 0
        assert "No time logs or blocks found." in capsys.readouterr().out
