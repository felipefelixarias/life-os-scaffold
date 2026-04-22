"""Tests for ``01-ops/life-os/scripts/calendar_analytics.py``."""

from __future__ import annotations

import csv
import datetime as dt
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "01-ops" / "life-os" / "scripts" / "calendar_analytics.py"
SPEC = spec_from_file_location("life_os_calendar_analytics", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
calendar_analytics = module_from_spec(SPEC)
# Register before exec_module so @dataclass can resolve cls.__module__.
sys.modules[SPEC.name] = calendar_analytics
SPEC.loader.exec_module(calendar_analytics)


ANCHOR = dt.date(2026, 4, 22)  # Wednesday


CSV_HEADER = [
    "event_id",
    "date",
    "start_time",
    "end_time",
    "title",
    "location",
    "attendees",
    "source",
    "calendar",
    "notes",
]


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
        writer.writeheader()
        for r in rows:
            writer.writerow({col: r.get(col, "") for col in CSV_HEADER})


def _event(**overrides: Any) -> calendar_analytics.CalendarEvent:
    defaults: dict[str, Any] = {
        "event_id": "E-1",
        "date": ANCHOR,
        "start_time": dt.time(9, 0),
        "end_time": dt.time(10, 0),
        "title": "Sync",
        "location": None,
        "attendees": (),
        "source": "google_calendar",
        "calendar": "primary",
        "notes": None,
    }
    defaults.update(overrides)
    return calendar_analytics.CalendarEvent(**defaults)


# ----- event_duration_minutes -----------------------------------------------


def test_event_duration_minutes_basic() -> None:
    e = _event(start_time=dt.time(9, 0), end_time=dt.time(10, 30))
    assert calendar_analytics.event_duration_minutes(e) == 90


def test_event_duration_minutes_zero_length() -> None:
    e = _event(start_time=dt.time(9, 0), end_time=dt.time(9, 0))
    assert calendar_analytics.event_duration_minutes(e) == 0


def test_event_duration_minutes_crossing_midnight() -> None:
    e = _event(start_time=dt.time(23, 0), end_time=dt.time(1, 0))
    assert calendar_analytics.event_duration_minutes(e) == 120


# ----- format_duration ------------------------------------------------------


@pytest.mark.parametrize(
    ("mins", "expected"),
    [
        (0, "0m"),
        (-5, "0m"),
        (45, "45m"),
        (60, "1h"),
        (75, "1h 15m"),
        (605, "10h 05m"),
    ],
)
def test_format_duration(mins: int, expected: str) -> None:
    assert calendar_analytics.format_duration(mins) == expected


# ----- load_calendar_events -------------------------------------------------


def test_load_calendar_events_parses_rows(tmp_path: Path) -> None:
    csv_path = tmp_path / "events.csv"
    _write_csv(
        csv_path,
        [
            {
                "event_id": "E-1",
                "date": "2026-04-22",
                "start_time": "09:00",
                "end_time": "10:00",
                "title": "Standup",
                "location": "Zoom",
                "attendees": "alice@x.com, bob@x.com",
                "source": "google_calendar",
                "calendar": "work",
                "notes": "",
            },
        ],
    )
    events = calendar_analytics.load_calendar_events(csv_path)
    assert len(events) == 1
    e = events[0]
    assert e.event_id == "E-1"
    assert e.date == dt.date(2026, 4, 22)
    assert e.start_time == dt.time(9, 0)
    assert e.end_time == dt.time(10, 0)
    assert e.attendees == ("alice@x.com", "bob@x.com")
    assert e.source == "google_calendar"
    assert e.calendar == "work"
    assert e.notes is None  # empty string normalized to None


def test_load_calendar_events_skips_blank_rows(tmp_path: Path) -> None:
    csv_path = tmp_path / "events.csv"
    _write_csv(
        csv_path,
        [
            {
                "event_id": "E-1",
                "date": "2026-04-22",
                "start_time": "09:00",
                "end_time": "10:00",
                "title": "Real",
            },
            {"event_id": "", "date": "", "start_time": "", "end_time": "", "title": ""},
        ],
    )
    events = calendar_analytics.load_calendar_events(csv_path)
    assert [e.event_id for e in events] == ["E-1"]


def test_load_calendar_events_short_row_missing_optional_fields(
    tmp_path: Path,
) -> None:
    # Fewer fields than the header → DictReader fills missing cells with None.
    # `_maybe` must map None → None without raising.
    csv_path = tmp_path / "events.csv"
    csv_path.write_text(
        "event_id,date,start_time,end_time,title,location,attendees,source,calendar,notes\n"
        "E-short,2026-04-22,09:00,10:00,Short\n",
        encoding="utf-8",
    )
    events = calendar_analytics.load_calendar_events(csv_path)
    assert len(events) == 1
    assert events[0].location is None
    assert events[0].attendees == ()
    assert events[0].source is None
    assert events[0].calendar is None
    assert events[0].notes is None


def test_load_calendar_events_empty_attendees(tmp_path: Path) -> None:
    csv_path = tmp_path / "events.csv"
    _write_csv(
        csv_path,
        [
            {
                "event_id": "E-1",
                "date": "2026-04-22",
                "start_time": "09:00",
                "end_time": "10:00",
                "title": "Solo",
                "attendees": "",
            },
        ],
    )
    events = calendar_analytics.load_calendar_events(csv_path)
    assert events[0].attendees == ()


def test_load_calendar_events_raises_on_bad_date(tmp_path: Path) -> None:
    csv_path = tmp_path / "events.csv"
    _write_csv(
        csv_path,
        [
            {
                "event_id": "E-1",
                "date": "not-a-date",
                "start_time": "09:00",
                "end_time": "10:00",
                "title": "x",
            },
        ],
    )
    with pytest.raises(ValueError, match="not-a-date"):
        calendar_analytics.load_calendar_events(csv_path)


# ----- compute_source_stats -------------------------------------------------


def test_compute_source_stats_windows_and_top_location() -> None:
    events = [
        _event(
            event_id="E-today",
            date=ANCHOR,
            start_time=dt.time(9, 0),
            end_time=dt.time(10, 30),
            location="HQ",
        ),
        _event(
            event_id="E-week",
            date=ANCHOR - dt.timedelta(days=2),  # Monday of same ISO week
            start_time=dt.time(14, 0),
            end_time=dt.time(15, 0),
            location="HQ",
        ),
        _event(
            event_id="E-month",
            date=ANCHOR - dt.timedelta(days=20),
            start_time=dt.time(11, 0),
            end_time=dt.time(12, 0),
            location="Remote",
        ),
        _event(
            event_id="E-outside-month",
            date=ANCHOR - dt.timedelta(days=45),
            start_time=dt.time(9, 0),
            end_time=dt.time(10, 0),
            location="HQ",
        ),
        _event(
            event_id="E-other-source",
            date=ANCHOR,
            start_time=dt.time(13, 0),
            end_time=dt.time(14, 0),
            source="outlook",
        ),
    ]
    stats = calendar_analytics.compute_source_stats("google_calendar", events, ANCHOR)

    assert stats.source == "google_calendar"
    assert stats.today_events == 1
    assert stats.today_minutes == 90
    assert stats.week_events == 2
    assert stats.week_minutes == 150
    # 3 google events fall within the last 30 days (today + week + month ones).
    assert stats.month_events == 3
    assert stats.month_minutes == 90 + 60 + 60
    assert stats.unique_calendars == 1  # all three within-month are "primary"
    assert stats.top_location == "HQ"
    assert stats.top_location_count == 2


def test_compute_source_stats_no_matches() -> None:
    events = [_event(source="google_calendar")]
    stats = calendar_analytics.compute_source_stats("manual", events, ANCHOR)
    assert stats.today_events == 0
    assert stats.month_events == 0
    assert stats.top_location is None
    assert stats.unique_calendars == 0


# ----- analyze --------------------------------------------------------------


def _write_events_csv(tmp_path: Path) -> Path:
    csv_path = tmp_path / "events.csv"
    _write_csv(
        csv_path,
        [
            # Today, 09:00-10:30, google/primary, location HQ
            {
                "event_id": "E-1",
                "date": ANCHOR.isoformat(),
                "start_time": "09:00",
                "end_time": "10:30",
                "title": "Today",
                "location": "HQ",
                "source": "google_calendar",
                "calendar": "primary",
            },
            # 5 days ago (same ISO week not guaranteed — ANCHOR is Wed so 5d
            # back is previous Fri, outside the week window, still inside month)
            {
                "event_id": "E-2",
                "date": (ANCHOR - dt.timedelta(days=5)).isoformat(),
                "start_time": "13:00",
                "end_time": "14:00",
                "title": "Past",
                "location": "HQ",
                "source": "google_calendar",
                "calendar": "primary",
            },
            # Yesterday, manual, different calendar/location
            {
                "event_id": "E-3",
                "date": (ANCHOR - dt.timedelta(days=1)).isoformat(),
                "start_time": "16:00",
                "end_time": "17:00",
                "title": "Dentist",
                "location": "Clinic",
                "source": "manual",
                "calendar": "personal",
            },
            # Outside 30-day window
            {
                "event_id": "E-4",
                "date": (ANCHOR - dt.timedelta(days=40)).isoformat(),
                "start_time": "09:00",
                "end_time": "10:00",
                "title": "Old",
                "location": "HQ",
                "source": "google_calendar",
                "calendar": "primary",
            },
            # Missing source → unknown bucket
            {
                "event_id": "E-5",
                "date": (ANCHOR - dt.timedelta(days=2)).isoformat(),
                "start_time": "08:00",
                "end_time": "08:30",
                "title": "Imported",
            },
        ],
    )
    return csv_path


def test_analyze_end_to_end(tmp_path: Path) -> None:
    csv_path = _write_events_csv(tmp_path)
    report = calendar_analytics.analyze(csv_path, today=ANCHOR)

    assert report.anchor_date == ANCHOR
    assert report.week_start == ANCHOR - dt.timedelta(days=ANCHOR.weekday())
    assert report.month_start == ANCHOR - dt.timedelta(
        days=calendar_analytics.MONTH_WINDOW_DAYS - 1
    )

    # Today: only E-1 (90 min)
    assert report.total_events_today == 1
    assert report.total_minutes_today == 90

    # Week (Mon..Wed): E-1 today, E-3 yesterday, E-5 Monday → 3 events
    assert report.total_events_week == 3

    # Month: E-1, E-2, E-3, E-5 (E-4 is 40d out)
    assert report.total_events_month == 4
    assert report.total_minutes_month == 90 + 60 + 60 + 30

    # events_per_day_avg: 4 events over 4 active days = 1.0
    assert report.events_per_day_avg == pytest.approx(1.0)

    # Sources: google_calendar + manual + unknown, sorted alphabetically
    names = [s.source for s in report.sources]
    assert names == ["google_calendar", "manual", calendar_analytics.UNKNOWN_SOURCE]

    # Top location: HQ appears twice in month window
    assert report.top_location == "HQ"
    assert report.top_location_count == 2

    # Top calendar: "primary" appears twice (E-1, E-2) — tie-break via Counter.most_common
    assert report.top_calendar == "primary"

    # Busiest weekday: within month window, find the weekday with max minutes.
    # Weekdays: Wed (E-1, 90), Fri (E-2, 60), Tue (E-3, 60), Mon (E-5, 30) → Wed.
    assert report.busiest_weekday == "Wed"
    assert report.busiest_weekday_minutes == 90


def test_analyze_missing_csv_yields_empty_report(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.csv"
    report = calendar_analytics.analyze(missing, today=ANCHOR)
    assert report.total_events_month == 0
    assert report.sources == []
    assert report.busiest_weekday is None
    assert report.top_location is None
    assert report.top_calendar is None


def test_analyze_empty_csv_yields_empty_report(tmp_path: Path) -> None:
    csv_path = tmp_path / "events.csv"
    _write_csv(csv_path, rows=[])
    report = calendar_analytics.analyze(csv_path, today=ANCHOR)
    assert report.total_events_today == 0
    assert report.events_per_day_avg == 0.0
    assert report.busiest_weekday is None


def test_analyze_uses_today_when_anchor_not_given(tmp_path: Path) -> None:
    csv_path = tmp_path / "events.csv"
    _write_csv(csv_path, rows=[])
    report = calendar_analytics.analyze(csv_path)
    assert report.anchor_date == dt.date.today()


# ----- format_report --------------------------------------------------------


def test_format_report_contains_headline_and_source_table(tmp_path: Path) -> None:
    csv_path = _write_events_csv(tmp_path)
    report = calendar_analytics.analyze(csv_path, today=ANCHOR)
    out = calendar_analytics.format_report(report)

    assert "Calendar Analytics — anchor 2026-04-22" in out
    assert "Today: 1 events" in out
    assert "google_calendar" in out
    assert "manual" in out
    assert "Busiest weekday (last 30d): Wed" in out
    assert "Top location (last 30d): HQ" in out
    assert "Top calendar (last 30d): primary" in out


def test_format_report_empty(tmp_path: Path) -> None:
    csv_path = tmp_path / "events.csv"
    _write_csv(csv_path, rows=[])
    report = calendar_analytics.analyze(csv_path, today=ANCHOR)
    out = calendar_analytics.format_report(report)
    assert "(no events found)" in out
    assert "Busiest weekday" not in out
    assert "Top location" not in out
    assert "Top calendar" not in out


# ----- CLI ------------------------------------------------------------------


def test_main_cli_reads_csv_and_anchor(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    csv_path = _write_events_csv(tmp_path)
    rc = calendar_analytics.main(
        ["--csv", str(csv_path), "--today", ANCHOR.isoformat()]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "Calendar Analytics — anchor 2026-04-22" in out
    assert "google_calendar" in out


def test_main_cli_handles_missing_csv(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = calendar_analytics.main(
        [
            "--csv",
            str(tmp_path / "missing.csv"),
            "--today",
            ANCHOR.isoformat(),
        ]
    )
    assert rc == 0
    assert "(no events found)" in capsys.readouterr().out
