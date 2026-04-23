from __future__ import annotations

import csv
import datetime as dt
import io
import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "01-ops" / "life-os" / "scripts" / "export_ical.py"
SPEC = spec_from_file_location("life_os_export_ical", MODULE_PATH)
export_ical = module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(export_ical)


FIXED_NOW = dt.datetime(2026, 4, 23, 18, 30, 0, tzinfo=dt.UTC)


def _unfold(body: str) -> str:
    """Reverse RFC 5545 line folding so substring assertions don't false-fail
    when the content line crosses the 75-octet boundary."""
    return body.replace("\r\n ", "")


def _write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


def _time_blocks_csv(path: Path, rows: list[list[str]]) -> None:
    _write_csv(
        path,
        [
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
        ],
        rows,
    )


def _calendar_events_csv(path: Path, rows: list[list[str]]) -> None:
    _write_csv(
        path,
        [
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
        ],
        rows,
    )


class TestFormatUtc:
    def test_naive_datetime_gets_converted(self):
        naive = dt.datetime(2026, 5, 10, 9, 0, 0)
        # Naive datetime's astimezone assumes local time — we only care the call
        # path is exercised and produces an RFC 5545 shape.
        out = export_ical._format_utc(naive)
        assert out.endswith("Z")
        assert len(out) == len("YYYYMMDDTHHMMSSZ")

    def test_non_utc_aware_datetime_is_normalized(self):
        aware = dt.datetime(
            2026, 5, 10, 9, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles")
        )
        # 09:00 PDT → 16:00 UTC
        assert export_ical._format_utc(aware) == "20260510T160000Z"

    def test_utc_datetime_passes_through(self):
        utc = dt.datetime(2026, 5, 10, 9, 0, 0, tzinfo=dt.UTC)
        assert export_ical._format_utc(utc) == "20260510T090000Z"


class TestEscapeText:
    def test_escapes_semicolons_and_commas(self):
        assert export_ical.escape_text("a;b,c") == "a\\;b\\,c"

    def test_escapes_newlines_to_literal_backslash_n(self):
        assert export_ical.escape_text("line1\nline2") == "line1\\nline2"

    def test_escapes_crlf_and_cr(self):
        assert export_ical.escape_text("a\r\nb") == "a\\nb"
        assert export_ical.escape_text("a\rb") == "a\\nb"

    def test_backslash_escaped_first_to_avoid_double_escape(self):
        # Input backslash must become a literal pair of backslashes,
        # not get rewritten by a subsequent substitution.
        assert export_ical.escape_text("a\\;b") == "a\\\\\\;b"


class TestFoldLine:
    def test_short_line_unchanged(self):
        line = "SUMMARY:short value"
        assert export_ical.fold_line(line) == line

    def test_long_line_gets_folded_with_crlf_space(self):
        line = "DESCRIPTION:" + ("x" * 200)
        out = export_ical.fold_line(line)
        assert "\r\n " in out
        # Reassembling (remove CRLF+space) must give the original content.
        assert out.replace("\r\n ", "") == line

    def test_no_segment_exceeds_75_octets(self):
        line = "DESCRIPTION:" + ("x" * 500)
        out = export_ical.fold_line(line)
        for segment in out.split("\r\n"):
            # Continuation segments are prefixed by a single leading space
            # which still counts toward the 75-octet limit.
            assert len(segment.encode("utf-8")) <= 75

    def test_multibyte_characters_not_split_mid_codepoint(self):
        line = "SUMMARY:" + ("é" * 60)
        out = export_ical.fold_line(line)
        # Re-decoding must succeed — a mid-codepoint split would raise.
        rejoined = out.replace("\r\n ", "")
        assert rejoined == line
        for segment in out.split("\r\n"):
            segment.encode("utf-8").decode("utf-8")


class TestLoadTimezone:
    def test_reads_timezone_from_profile(self, tmp_path: Path):
        profile = tmp_path / "profile.json"
        profile.write_text(json.dumps({"timezone": "America/New_York"}))
        tz = export_ical.load_timezone(profile)
        assert tz == ZoneInfo("America/New_York")

    def test_missing_profile_falls_back_to_default(self, tmp_path: Path):
        missing = tmp_path / "nonexistent.json"
        tz = export_ical.load_timezone(missing)
        assert tz == ZoneInfo(export_ical.DEFAULT_TIMEZONE)

    def test_malformed_profile_falls_back_to_default(self, tmp_path: Path):
        profile = tmp_path / "profile.json"
        profile.write_text("{not-valid-json")
        tz = export_ical.load_timezone(profile)
        assert tz == ZoneInfo(export_ical.DEFAULT_TIMEZONE)

    def test_unknown_timezone_falls_back_to_default(self, tmp_path: Path):
        profile = tmp_path / "profile.json"
        profile.write_text(json.dumps({"timezone": "Not/A_Real_Zone"}))
        tz = export_ical.load_timezone(profile)
        assert tz == ZoneInfo(export_ical.DEFAULT_TIMEZONE)


class TestTimeBlockToVevent:
    def test_full_row_emits_all_expected_properties(self):
        tz = ZoneInfo("America/Los_Angeles")
        row = {
            "block_id": "B-001",
            "date": "2026-05-10",
            "start": "09:00",
            "end": "10:30",
            "title": "Deep work",
            "domain": "career",
            "task_id": "T-42",
            "source": "auto_planner",
            "status": "planned",
            "notes": "Protect this block",
        }
        lines = export_ical.time_block_to_vevent(row, tz, FIXED_NOW)
        assert lines is not None
        body = "\r\n".join(lines)
        assert "BEGIN:VEVENT" in body
        assert "UID:B-001@life-os" in body
        assert "DTSTAMP:20260423T183000Z" in body
        # 2026-05-10 09:00 America/Los_Angeles is PDT (UTC-7) → 16:00 UTC.
        assert "DTSTART:20260510T160000Z" in body
        assert "DTEND:20260510T173000Z" in body
        assert "SUMMARY:[career] Deep work" in body
        assert "CATEGORIES:career" in body
        assert "Task: T-42" in body
        assert "Source: auto_planner" in body
        assert "Status: planned" in body
        assert lines[-1] == "END:VEVENT"

    def test_missing_block_id_is_skipped(self):
        tz = ZoneInfo("America/Los_Angeles")
        row = {
            "block_id": "",
            "date": "2026-05-10",
            "start": "09:00",
            "end": "10:00",
            "title": "Anon",
        }
        assert export_ical.time_block_to_vevent(row, tz, FIXED_NOW) is None

    def test_invalid_time_is_skipped(self):
        tz = ZoneInfo("America/Los_Angeles")
        row = {
            "block_id": "B-1",
            "date": "2026-05-10",
            "start": "not-a-time",
            "end": "10:00",
            "title": "Oops",
        }
        assert export_ical.time_block_to_vevent(row, tz, FIXED_NOW) is None

    def test_invalid_end_time_is_skipped(self):
        tz = ZoneInfo("America/Los_Angeles")
        row = {
            "block_id": "B-1",
            "date": "2026-05-10",
            "start": "09:00",
            "end": "99:99",
            "title": "Oops",
        }
        assert export_ical.time_block_to_vevent(row, tz, FIXED_NOW) is None

    def test_missing_end_time_gets_one_hour_default(self):
        tz = ZoneInfo("America/Los_Angeles")
        row = {
            "block_id": "B-1",
            "date": "2026-05-10",
            "start": "09:00",
            "end": "",
            "title": "Open",
        }
        lines = export_ical.time_block_to_vevent(row, tz, FIXED_NOW)
        assert lines is not None
        body = "\r\n".join(lines)
        # 09:00 PDT → 16:00 UTC; default end = start + 1h
        assert "DTSTART:20260510T160000Z" in body
        assert "DTEND:20260510T170000Z" in body

    def test_missing_date_skipped(self):
        tz = ZoneInfo("America/Los_Angeles")
        row = {
            "block_id": "B-1",
            "date": "",
            "start": "09:00",
            "end": "10:00",
            "title": "x",
        }
        assert export_ical.time_block_to_vevent(row, tz, FIXED_NOW) is None

    def test_invalid_date_skipped(self):
        tz = ZoneInfo("America/Los_Angeles")
        row = {
            "block_id": "B-1",
            "date": "not-a-date",
            "start": "09:00",
            "end": "10:00",
            "title": "x",
        }
        assert export_ical.time_block_to_vevent(row, tz, FIXED_NOW) is None

    def test_end_before_start_rolls_to_next_day(self):
        tz = ZoneInfo("America/Los_Angeles")
        row = {
            "block_id": "B-2",
            "date": "2026-05-10",
            "start": "23:00",
            "end": "01:00",
            "title": "Night owl",
        }
        lines = export_ical.time_block_to_vevent(row, tz, FIXED_NOW)
        assert lines is not None
        body = "\r\n".join(lines)
        # 23:00 PDT (UTC-7) → 06:00 UTC next day
        assert "DTSTART:20260511T060000Z" in body
        # 01:00 PDT next day (UTC-7) → 08:00 UTC on the 11th
        assert "DTEND:20260511T080000Z" in body

    def test_no_domain_omits_brackets_and_categories(self):
        tz = ZoneInfo("America/Los_Angeles")
        row = {
            "block_id": "B-3",
            "date": "2026-05-10",
            "start": "09:00",
            "end": "10:00",
            "title": "Plain title",
        }
        lines = export_ical.time_block_to_vevent(row, tz, FIXED_NOW)
        assert lines is not None
        body = "\r\n".join(lines)
        assert "SUMMARY:Plain title" in body
        assert "CATEGORIES:" not in body


class TestCalendarEventToVevent:
    def test_full_row_emits_all_expected_properties(self):
        tz = ZoneInfo("America/Los_Angeles")
        row = {
            "event_id": "E-100",
            "date": "2026-05-10",
            "start_time": "14:00",
            "end_time": "15:00",
            "title": "Team meeting",
            "location": "Conference Room A",
            "attendees": "alice@example.com, bob@example.com",
            "source": "google_calendar",
            "calendar": "primary",
            "notes": "Weekly sync",
        }
        lines = export_ical.calendar_event_to_vevent(row, tz, FIXED_NOW)
        assert lines is not None
        body = _unfold("\r\n".join(lines))
        assert "UID:E-100@life-os" in body
        # 2026-05-10 14:00 PDT → 21:00 UTC
        assert "DTSTART:20260510T210000Z" in body
        assert "DTEND:20260510T220000Z" in body
        assert "SUMMARY:Team meeting" in body
        assert "LOCATION:Conference Room A" in body
        assert "Attendees: alice@example.com\\, bob@example.com" in body
        assert "Calendar: primary" in body

    def test_missing_event_id_skipped(self):
        tz = ZoneInfo("America/Los_Angeles")
        assert (
            export_ical.calendar_event_to_vevent(
                {"event_id": "", "date": "2026-05-10", "title": "x"},
                tz,
                FIXED_NOW,
            )
            is None
        )

    def test_missing_date_skipped(self):
        tz = ZoneInfo("America/Los_Angeles")
        row = {
            "event_id": "E-1",
            "date": "",
            "start_time": "09:00",
            "end_time": "10:00",
            "title": "x",
        }
        assert export_ical.calendar_event_to_vevent(row, tz, FIXED_NOW) is None

    def test_invalid_date_skipped(self):
        tz = ZoneInfo("America/Los_Angeles")
        row = {
            "event_id": "E-1",
            "date": "not-a-date",
            "start_time": "09:00",
            "end_time": "10:00",
            "title": "x",
        }
        assert export_ical.calendar_event_to_vevent(row, tz, FIXED_NOW) is None

    def test_missing_end_time_gets_one_hour_default(self):
        tz = ZoneInfo("America/Los_Angeles")
        row = {
            "event_id": "E-2",
            "date": "2026-05-10",
            "start_time": "09:00",
            "end_time": "",
            "title": "Open-ended",
        }
        lines = export_ical.calendar_event_to_vevent(row, tz, FIXED_NOW)
        assert lines is not None
        body = "\r\n".join(lines)
        assert "DTSTART:20260510T160000Z" in body
        assert "DTEND:20260510T170000Z" in body


class TestBuildCalendar:
    def test_empty_sources_produce_valid_wrapper(self):
        tz = ZoneInfo("UTC")
        doc = export_ical.build_calendar(
            time_blocks=[], calendar_events=[], tz=tz, now=FIXED_NOW
        )
        assert doc.startswith("BEGIN:VCALENDAR\r\n")
        assert doc.endswith("END:VCALENDAR\r\n")
        assert "VERSION:2.0" in doc
        assert f"PRODID:{export_ical.PRODID}" in doc
        assert "BEGIN:VEVENT" not in doc

    def test_mixed_sources_emits_both_event_types(self):
        tz = ZoneInfo("UTC")
        blocks = [
            {
                "block_id": "B-1",
                "date": "2026-05-10",
                "start": "09:00",
                "end": "10:00",
                "title": "Block A",
                "domain": "work",
                "task_id": "",
                "source": "manual",
                "status": "planned",
                "notes": "",
            }
        ]
        events = [
            {
                "event_id": "E-1",
                "date": "2026-05-10",
                "start_time": "11:00",
                "end_time": "12:00",
                "title": "Event A",
                "location": "",
                "attendees": "",
                "source": "manual",
                "calendar": "primary",
                "notes": "",
            }
        ]
        doc = export_ical.build_calendar(
            time_blocks=blocks, calendar_events=events, tz=tz, now=FIXED_NOW
        )
        assert doc.count("BEGIN:VEVENT") == 2
        assert "UID:B-1@life-os" in doc
        assert "UID:E-1@life-os" in doc

    def test_date_range_filters_out_events_outside_window(self):
        tz = ZoneInfo("UTC")
        blocks = [
            {
                "block_id": f"B-{i}",
                "date": day,
                "start": "09:00",
                "end": "10:00",
                "title": f"Block {i}",
                "domain": "",
                "task_id": "",
                "source": "",
                "status": "",
                "notes": "",
            }
            for i, day in enumerate(["2026-05-01", "2026-05-15", "2026-05-31"])
        ]
        doc = export_ical.build_calendar(
            time_blocks=blocks,
            tz=tz,
            start=dt.date(2026, 5, 10),
            end=dt.date(2026, 5, 20),
            now=FIXED_NOW,
        )
        assert "UID:B-0@life-os" not in doc
        assert "UID:B-1@life-os" in doc
        assert "UID:B-2@life-os" not in doc

    def test_date_range_filters_calendar_events(self):
        tz = ZoneInfo("UTC")
        events = [
            {
                "event_id": "E-IN",
                "date": "2026-05-15",
                "start_time": "09:00",
                "end_time": "10:00",
                "title": "In",
                "location": "",
                "attendees": "",
                "source": "",
                "calendar": "",
                "notes": "",
            },
            {
                "event_id": "E-OUT",
                "date": "2026-06-01",
                "start_time": "09:00",
                "end_time": "10:00",
                "title": "Out",
                "location": "",
                "attendees": "",
                "source": "",
                "calendar": "",
                "notes": "",
            },
        ]
        doc = export_ical.build_calendar(
            calendar_events=events,
            tz=tz,
            start=dt.date(2026, 5, 1),
            end=dt.date(2026, 5, 31),
            now=FIXED_NOW,
        )
        assert "UID:E-IN@life-os" in doc
        assert "UID:E-OUT@life-os" not in doc

    def test_range_filter_drops_rows_with_missing_dates(self):
        tz = ZoneInfo("UTC")
        blocks = [
            {
                "block_id": "B-EMPTY",
                "date": "",
                "start": "09:00",
                "end": "10:00",
                "title": "x",
                "domain": "",
                "task_id": "",
                "source": "",
                "status": "",
                "notes": "",
            }
        ]
        doc = export_ical.build_calendar(
            time_blocks=blocks,
            tz=tz,
            start=dt.date(2026, 1, 1),
            end=dt.date(2026, 12, 31),
            now=FIXED_NOW,
        )
        assert "UID:B-EMPTY@life-os" not in doc

    def test_range_filter_drops_rows_with_unparseable_dates(self):
        tz = ZoneInfo("UTC")
        blocks = [
            {
                "block_id": "B-BAD",
                "date": "not-a-date",
                "start": "09:00",
                "end": "10:00",
                "title": "x",
                "domain": "",
                "task_id": "",
                "source": "",
                "status": "",
                "notes": "",
            }
        ]
        doc = export_ical.build_calendar(
            time_blocks=blocks,
            tz=tz,
            start=dt.date(2026, 1, 1),
            end=dt.date(2026, 12, 31),
            now=FIXED_NOW,
        )
        assert "UID:B-BAD@life-os" not in doc

    def test_uses_crlf_line_endings_per_rfc5545(self):
        doc = export_ical.build_calendar(
            time_blocks=[], calendar_events=[], tz=ZoneInfo("UTC"), now=FIXED_NOW
        )
        # Every content line must be CRLF-terminated; no bare LFs.
        assert "\n" in doc
        assert doc.replace("\r\n", "") == doc.replace("\r\n", "").replace("\n", "")


class TestExportIcalIntegration:
    def test_end_to_end_from_csv_files(self, tmp_path: Path):
        tb = tmp_path / "time_blocks.csv"
        ce = tmp_path / "calendar_events.csv"
        _time_blocks_csv(
            tb,
            [
                [
                    "B-1",
                    "2026-05-10",
                    "09:00",
                    "10:00",
                    "Focus",
                    "career",
                    "",
                    "manual",
                    "planned",
                    "",
                ]
            ],
        )
        _calendar_events_csv(
            ce,
            [
                [
                    "E-1",
                    "2026-05-10",
                    "14:00",
                    "15:00",
                    "Sync",
                    "Zoom",
                    "",
                    "manual",
                    "primary",
                    "",
                ]
            ],
        )
        doc = export_ical.export_ical(
            source="both",
            time_blocks_path=tb,
            calendar_events_path=ce,
            tz=ZoneInfo("UTC"),
            now=FIXED_NOW,
        )
        assert "UID:B-1@life-os" in doc
        assert "UID:E-1@life-os" in doc

    def test_missing_source_file_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            export_ical.export_ical(
                source="time_blocks",
                time_blocks_path=tmp_path / "missing.csv",
                tz=ZoneInfo("UTC"),
                now=FIXED_NOW,
            )

    def test_unknown_source_rejected(self, tmp_path: Path):
        with pytest.raises(ValueError, match="Unknown source"):
            export_ical.export_ical(
                source="invalid",  # type: ignore[arg-type]
                time_blocks_path=tmp_path / "x.csv",
                calendar_events_path=tmp_path / "y.csv",
                tz=ZoneInfo("UTC"),
                now=FIXED_NOW,
            )


class TestCli:
    def test_stdout_mode_writes_ics_document(self, tmp_path: Path, monkeypatch):
        tb = tmp_path / "time_blocks.csv"
        ce = tmp_path / "calendar_events.csv"
        _time_blocks_csv(
            tb,
            [
                [
                    "B-CLI",
                    "2026-05-10",
                    "09:00",
                    "10:00",
                    "CLI block",
                    "",
                    "",
                    "",
                    "",
                    "",
                ]
            ],
        )
        _calendar_events_csv(ce, [])
        monkeypatch.setattr(export_ical, "TIME_BLOCKS_CSV", tb)
        monkeypatch.setattr(export_ical, "CALENDAR_EVENTS_CSV", ce)

        buf = io.StringIO()
        rc = export_ical.main(["--source", "both"], stdout=buf)
        assert rc == 0
        out = buf.getvalue()
        assert "BEGIN:VCALENDAR" in out
        assert "UID:B-CLI@life-os" in out

    def test_output_flag_writes_file(self, tmp_path: Path, monkeypatch):
        tb = tmp_path / "time_blocks.csv"
        ce = tmp_path / "calendar_events.csv"
        _time_blocks_csv(
            tb,
            [
                [
                    "B-FILE",
                    "2026-05-10",
                    "09:00",
                    "10:00",
                    "File block",
                    "",
                    "",
                    "",
                    "",
                    "",
                ]
            ],
        )
        _calendar_events_csv(ce, [])
        monkeypatch.setattr(export_ical, "TIME_BLOCKS_CSV", tb)
        monkeypatch.setattr(export_ical, "CALENDAR_EVENTS_CSV", ce)

        out_path = tmp_path / "out" / "calendar.ics"
        rc = export_ical.main(["--source", "time_blocks", "--output", str(out_path)])
        assert rc == 0
        text = out_path.read_text(encoding="utf-8")
        assert "UID:B-FILE@life-os" in text

    def test_missing_source_file_returns_nonzero(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(export_ical, "TIME_BLOCKS_CSV", tmp_path / "nope.csv")
        buf = io.StringIO()
        rc = export_ical.main(["--source", "time_blocks"], stdout=buf)
        assert rc == 1

    def test_invalid_date_argument_exits_with_code_2(self, tmp_path: Path):
        with pytest.raises(SystemExit) as exc:
            export_ical.main(["--start-date", "not-a-date"])
        assert exc.value.code == 2

    def test_start_after_end_rejected(self, tmp_path: Path):
        with pytest.raises(SystemExit) as exc:
            export_ical.main(["--start-date", "2026-06-01", "--end-date", "2026-05-01"])
        assert exc.value.code == 2

    def test_unknown_source_returns_one(self, monkeypatch):
        # CLI's argparse accepts only valid choices, so smuggle the bad value
        # in via the underlying export_ical() to exercise the ValueError branch.
        def _bad(*args, **kwargs):
            raise ValueError("Unknown source 'xyz'")

        monkeypatch.setattr(export_ical, "export_ical", _bad)
        rc = export_ical.main(["--source", "both"], stdout=io.StringIO())
        assert rc == 1

    def test_date_range_filters_on_cli(self, tmp_path: Path, monkeypatch):
        tb = tmp_path / "time_blocks.csv"
        ce = tmp_path / "calendar_events.csv"
        _time_blocks_csv(
            tb,
            [
                ["B-EARLY", "2026-01-01", "09:00", "10:00", "E", "", "", "", "", ""],
                ["B-MID", "2026-05-15", "09:00", "10:00", "M", "", "", "", "", ""],
                ["B-LATE", "2026-12-31", "09:00", "10:00", "L", "", "", "", "", ""],
            ],
        )
        _calendar_events_csv(ce, [])
        monkeypatch.setattr(export_ical, "TIME_BLOCKS_CSV", tb)
        monkeypatch.setattr(export_ical, "CALENDAR_EVENTS_CSV", ce)

        buf = io.StringIO()
        rc = export_ical.main(
            [
                "--source",
                "time_blocks",
                "--start-date",
                "2026-05-01",
                "--end-date",
                "2026-05-31",
            ],
            stdout=buf,
        )
        assert rc == 0
        out = buf.getvalue()
        assert "UID:B-EARLY@life-os" not in out
        assert "UID:B-MID@life-os" in out
        assert "UID:B-LATE@life-os" not in out
