"""Unit tests for ``habit_analytics.py``."""

from __future__ import annotations

import sys
from datetime import date
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "01-ops" / "life-os" / "scripts" / "habit_analytics.py"
MODULE_NAME = "life_os_habit_analytics"

SPEC = spec_from_file_location(MODULE_NAME, MODULE_PATH)
habit_analytics = module_from_spec(SPEC)
assert SPEC.loader is not None
# Register before exec_module — dataclasses resolve their module via sys.modules.
sys.modules[MODULE_NAME] = habit_analytics
SPEC.loader.exec_module(habit_analytics)

Habit = habit_analytics.Habit
LogEntry = habit_analytics.LogEntry


HABITS_HEADER = "habit_id,area,name,frequency,target_per_week,min_value,unit,active,notes,last_updated"
LOG_HEADER = "date,habit_id,value,notes"


def _write_habits(path: Path, rows: list[str]) -> None:
    path.write_text("\n".join([HABITS_HEADER, *rows]) + "\n", encoding="utf-8")


def _write_log(path: Path, rows: list[str]) -> None:
    path.write_text("\n".join([LOG_HEADER, *rows]) + "\n", encoding="utf-8")


def _make_habit(**overrides: object) -> Habit:
    defaults: dict[str, object] = {
        "habit_id": "exercise",
        "area": "health",
        "name": "Exercise",
        "frequency": "daily",
        "target_per_week": 5,
        "min_value": 1.0,
        "unit": "session",
        "active": True,
    }
    defaults.update(overrides)
    return Habit(**defaults)  # type: ignore[arg-type]


# --- load_habits ---------------------------------------------------------


def test_load_habits_parses_all_fields(tmp_path: Path) -> None:
    habits_path = tmp_path / "habits.csv"
    _write_habits(
        habits_path,
        [
            "sleep,health,Sleep,daily,7,7,hours,true,,2026-04-02",
            "meditate,health,Meditate,daily,5,10,minutes,false,,2026-04-02",
        ],
    )
    habits = habit_analytics.load_habits(habits_path)
    assert [h.habit_id for h in habits] == ["sleep", "meditate"]
    assert habits[0].target_per_week == 7
    assert habits[0].min_value == 7.0
    assert habits[0].active is True
    assert habits[1].active is False


def test_load_habits_missing_file_returns_empty(tmp_path: Path) -> None:
    assert habit_analytics.load_habits(tmp_path / "nope.csv") == []


def test_load_habits_skips_blank_habit_ids(tmp_path: Path) -> None:
    habits_path = tmp_path / "habits.csv"
    _write_habits(
        habits_path,
        [
            ",health,Nameless,daily,7,,,true,,2026-04-02",
            "read,growth,Read,daily,4,15,minutes,true,,2026-04-02",
        ],
    )
    habits = habit_analytics.load_habits(habits_path)
    assert [h.habit_id for h in habits] == ["read"]


def test_load_habits_handles_missing_numeric_fields(tmp_path: Path) -> None:
    habits_path = tmp_path / "habits.csv"
    _write_habits(
        habits_path,
        ["journal,growth,Journal,daily,,,,true,,2026-04-02"],
    )
    (habit,) = habit_analytics.load_habits(habits_path)
    assert habit.target_per_week == 7  # default
    assert habit.min_value is None
    assert habit.unit is None


def test_load_habits_tolerates_bad_numeric_values(tmp_path: Path) -> None:
    habits_path = tmp_path / "habits.csv"
    _write_habits(
        habits_path,
        ["x,health,X,daily,abc,xyz,,true,,2026-04-02"],
    )
    (habit,) = habit_analytics.load_habits(habits_path)
    assert habit.target_per_week == 7
    assert habit.min_value is None


# --- load_daily_log ------------------------------------------------------


def test_load_daily_log_parses_entries(tmp_path: Path) -> None:
    log_path = tmp_path / "daily_log.csv"
    _write_log(
        log_path,
        [
            "2026-04-20,sleep,7.5,ok",
            "2026-04-21,exercise,1,",
        ],
    )
    entries = habit_analytics.load_daily_log(log_path)
    assert len(entries) == 2
    assert entries[0].entry_date == date(2026, 4, 20)
    assert entries[0].value == 7.5


def test_load_daily_log_skips_bad_dates_and_blank_ids(tmp_path: Path) -> None:
    log_path = tmp_path / "daily_log.csv"
    _write_log(
        log_path,
        [
            "not-a-date,sleep,7.5,",
            "2026-04-21,,1,",
            "2026-04-21,exercise,1,",
        ],
    )
    entries = habit_analytics.load_daily_log(log_path)
    assert len(entries) == 1
    assert entries[0].habit_id == "exercise"


def test_load_daily_log_preserves_non_numeric_value_as_none(tmp_path: Path) -> None:
    log_path = tmp_path / "daily_log.csv"
    _write_log(log_path, ["2026-04-21,read,yes,"])
    (entry,) = habit_analytics.load_daily_log(log_path)
    assert entry.value is None


def test_load_daily_log_missing_file_returns_empty(tmp_path: Path) -> None:
    assert habit_analytics.load_daily_log(tmp_path / "missing.csv") == []


# --- is_completion -------------------------------------------------------


def test_is_completion_without_threshold_always_true() -> None:
    habit = _make_habit(min_value=None)
    entry = LogEntry(date(2026, 4, 21), "exercise", None)
    assert habit_analytics.is_completion(entry, habit) is True


def test_is_completion_requires_meeting_threshold() -> None:
    habit = _make_habit(min_value=10.0)
    below = LogEntry(date(2026, 4, 21), "exercise", 5.0)
    meets = LogEntry(date(2026, 4, 21), "exercise", 10.0)
    assert habit_analytics.is_completion(below, habit) is False
    assert habit_analytics.is_completion(meets, habit) is True


def test_is_completion_non_numeric_value_with_threshold_is_false() -> None:
    habit = _make_habit(min_value=10.0)
    entry = LogEntry(date(2026, 4, 21), "exercise", None)
    assert habit_analytics.is_completion(entry, habit) is False


# --- streak computation --------------------------------------------------


def test_current_streak_includes_today() -> None:
    today = date(2026, 4, 21)
    entries = [
        LogEntry(date(2026, 4, 19), "exercise", 1.0),
        LogEntry(date(2026, 4, 20), "exercise", 1.0),
        LogEntry(date(2026, 4, 21), "exercise", 1.0),
    ]
    stats = habit_analytics.compute_stats(_make_habit(), entries, today)
    assert stats.current_streak == 3


def test_current_streak_rolls_back_to_yesterday_if_today_missing() -> None:
    today = date(2026, 4, 22)
    entries = [
        LogEntry(date(2026, 4, 20), "exercise", 1.0),
        LogEntry(date(2026, 4, 21), "exercise", 1.0),
    ]
    stats = habit_analytics.compute_stats(_make_habit(), entries, today)
    assert stats.current_streak == 2


def test_current_streak_zero_when_two_day_gap() -> None:
    today = date(2026, 4, 23)
    entries = [LogEntry(date(2026, 4, 20), "exercise", 1.0)]
    stats = habit_analytics.compute_stats(_make_habit(), entries, today)
    assert stats.current_streak == 0


def test_longest_streak_finds_max_run() -> None:
    today = date(2026, 4, 30)
    # 3-day run then gap then 5-day run then gap then 2-day run
    completions = [
        *[date(2026, 4, i) for i in (1, 2, 3)],
        *[date(2026, 4, i) for i in (10, 11, 12, 13, 14)],
        *[date(2026, 4, i) for i in (20, 21)],
    ]
    entries = [LogEntry(d, "exercise", 1.0) for d in completions]
    stats = habit_analytics.compute_stats(_make_habit(), entries, today)
    assert stats.longest_streak == 5


def test_longest_streak_zero_when_no_completions() -> None:
    stats = habit_analytics.compute_stats(_make_habit(), [], date(2026, 4, 21))
    assert stats.longest_streak == 0
    assert stats.current_streak == 0
    assert stats.last_logged is None


def test_non_completion_entries_dont_extend_streak() -> None:
    habit = _make_habit(min_value=10.0)
    today = date(2026, 4, 21)
    entries = [
        LogEntry(date(2026, 4, 20), "exercise", 10.0),  # completes
        LogEntry(date(2026, 4, 21), "exercise", 3.0),  # below threshold
    ]
    stats = habit_analytics.compute_stats(habit, entries, today)
    # Today doesn't count, but yesterday does.
    assert stats.current_streak == 1


# --- adherence -----------------------------------------------------------


def test_week_adherence_uses_iso_week_starting_monday() -> None:
    # 2026-04-21 is a Tuesday; week starts Monday 2026-04-20.
    today = date(2026, 4, 21)
    entries = [
        LogEntry(date(2026, 4, 19), "exercise", 1.0),  # previous Sunday — excluded
        LogEntry(date(2026, 4, 20), "exercise", 1.0),
        LogEntry(date(2026, 4, 21), "exercise", 1.0),
    ]
    stats = habit_analytics.compute_stats(_make_habit(), entries, today)
    assert stats.week_completed == 2
    assert stats.week_target == 5
    assert stats.week_adherence == pytest.approx(2 / 5)


def test_month_adherence_uses_30_day_window() -> None:
    today = date(2026, 4, 30)
    # 31 days of completions; only the last 30 should count.
    entries = [
        LogEntry(date(2026, 3, 31) + _days(i), "exercise", 1.0) for i in range(31)
    ]
    stats = habit_analytics.compute_stats(_make_habit(), entries, today)
    assert stats.month_completed == 30


def test_adherence_clamps_to_one() -> None:
    habit = _make_habit(target_per_week=1)
    today = date(2026, 4, 26)  # Sunday
    # Completed every day this week (7), target is 1 — should cap at 1.0.
    week_start = date(2026, 4, 20)
    entries = [LogEntry(week_start + _days(i), "exercise", 1.0) for i in range(7)]
    stats = habit_analytics.compute_stats(habit, entries, today)
    assert stats.week_adherence == 1.0


def test_adherence_zero_target_returns_one() -> None:
    # Edge case — defensive handling for malformed schema.
    habit = _make_habit(target_per_week=0)
    stats = habit_analytics.compute_stats(habit, [], date(2026, 4, 21))
    assert stats.week_adherence == 1.0


def _days(n: int):
    from datetime import timedelta

    return timedelta(days=n)


# --- analyze + sorting ---------------------------------------------------


def test_analyze_filters_inactive_by_default(tmp_path: Path) -> None:
    habits_path = tmp_path / "habits.csv"
    log_path = tmp_path / "daily_log.csv"
    _write_habits(
        habits_path,
        [
            "active1,health,Active 1,daily,5,1,session,true,,2026-04-02",
            "retired,health,Retired,daily,5,1,session,false,,2026-04-02",
        ],
    )
    _write_log(log_path, [])
    stats = habit_analytics.analyze(habits_path, log_path, today=date(2026, 4, 21))
    assert [s.habit.habit_id for s in stats] == ["active1"]


def test_analyze_includes_inactive_when_requested(tmp_path: Path) -> None:
    habits_path = tmp_path / "habits.csv"
    log_path = tmp_path / "daily_log.csv"
    _write_habits(
        habits_path,
        [
            "a,health,A,daily,5,1,session,true,,2026-04-02",
            "b,health,B,daily,5,1,session,false,,2026-04-02",
        ],
    )
    _write_log(log_path, [])
    stats = habit_analytics.analyze(
        habits_path, log_path, today=date(2026, 4, 21), include_inactive=True
    )
    assert {s.habit.habit_id for s in stats} == {"a", "b"}


def test_analyze_sorts_by_current_streak_descending(tmp_path: Path) -> None:
    habits_path = tmp_path / "habits.csv"
    log_path = tmp_path / "daily_log.csv"
    _write_habits(
        habits_path,
        [
            "weak,health,Weak,daily,5,1,session,true,,2026-04-02",
            "strong,health,Strong,daily,5,1,session,true,,2026-04-02",
        ],
    )
    _write_log(
        log_path,
        [
            "2026-04-20,strong,1,",
            "2026-04-21,strong,1,",
        ],
    )
    stats = habit_analytics.analyze(habits_path, log_path, today=date(2026, 4, 21))
    assert [s.habit.habit_id for s in stats] == ["strong", "weak"]


# --- format_report -------------------------------------------------------


def test_format_report_contains_each_habit_name() -> None:
    stats = [
        habit_analytics.HabitStats(
            habit=_make_habit(habit_id="a", name="Alpha"),
            current_streak=3,
            longest_streak=5,
            week_completed=2,
            week_target=5,
            week_adherence=0.4,
            month_completed=10,
            month_target=21,
            month_adherence=0.47,
            last_logged=date(2026, 4, 21),
        ),
    ]
    report = habit_analytics.format_report(stats)
    assert "Alpha" in report
    assert "2026-04-21" in report
    assert "2/5" in report


def test_format_report_empty_returns_message() -> None:
    assert "No active habits" in habit_analytics.format_report([])


# --- CLI -----------------------------------------------------------------


def test_main_prints_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    habits_path = tmp_path / "habits.csv"
    log_path = tmp_path / "daily_log.csv"
    _write_habits(
        habits_path,
        ["x,health,X Habit,daily,5,1,session,true,,2026-04-02"],
    )
    _write_log(log_path, ["2026-04-21,x,1,"])

    exit_code = habit_analytics.main(
        [
            "--habits",
            str(habits_path),
            "--log",
            str(log_path),
            "--today",
            "2026-04-21",
        ]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "X Habit" in out
    assert "2026-04-21" in out


def test_main_include_inactive_flag(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    habits_path = tmp_path / "habits.csv"
    log_path = tmp_path / "daily_log.csv"
    _write_habits(
        habits_path,
        ["retired,health,Retired,daily,5,1,session,false,,2026-04-02"],
    )
    _write_log(log_path, [])

    habit_analytics.main(
        [
            "--habits",
            str(habits_path),
            "--log",
            str(log_path),
            "--today",
            "2026-04-21",
            "--include-inactive",
        ]
    )
    assert "Retired" in capsys.readouterr().out


def test_main_reports_no_habits_when_missing_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = habit_analytics.main(
        [
            "--habits",
            str(tmp_path / "none.csv"),
            "--log",
            str(tmp_path / "none.csv"),
            "--today",
            "2026-04-21",
        ]
    )
    assert exit_code == 0
    assert "No active habits" in capsys.readouterr().out
