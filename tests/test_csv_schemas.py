"""Tests for CSV schema definitions and validation."""

from __future__ import annotations

import sys
import tempfile
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "01-ops" / "life-os" / "scripts" / "csv_schemas.py"
SPEC = spec_from_file_location("csv_schemas", MODULE_PATH)
csv_schemas = module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["csv_schemas"] = csv_schemas
SPEC.loader.exec_module(csv_schemas)

ColumnSchema = csv_schemas.ColumnSchema
CSVSchema = csv_schemas.CSVSchema
SCHEMAS = csv_schemas.SCHEMAS
validate_csv = csv_schemas.validate_csv
validate_all = csv_schemas.validate_all


# ---------------------------------------------------------------------------
# Schema definition tests
# ---------------------------------------------------------------------------


def test_all_canonical_schemas_defined() -> None:
    """All expected canonical CSV types have a schema."""
    expected = {
        "tasks",
        "habits",
        "goals",
        "projects",
        "calendar_events",
        "time_blocks",
        "time_logs",
    }
    assert set(SCHEMAS.keys()) == expected


def test_schema_column_names_property() -> None:
    """CSVSchema.column_names returns names in order."""
    schema = SCHEMAS["habits"]
    assert schema.column_names[0] == "habit_id"
    assert "name" in schema.column_names


def test_schema_get_column() -> None:
    """CSVSchema.get_column looks up by name."""
    schema = SCHEMAS["tasks"]
    col = schema.get_column("status")
    assert col is not None
    assert col.dtype == "enum"
    assert "completed" in col.enum_values

    assert schema.get_column("nonexistent") is None


# ---------------------------------------------------------------------------
# Valid CSV passes
# ---------------------------------------------------------------------------


def _write_csv(directory: Path, name: str, lines: list[str]) -> Path:
    """Helper to write a CSV file from a list of lines."""
    p = directory / name
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def test_valid_tasks_csv() -> None:
    """A well-formed tasks CSV produces no errors."""
    with tempfile.TemporaryDirectory() as d:
        p = _write_csv(
            Path(d),
            "tasks.csv",
            [
                "task_id,project_id,title,domain,status,priority,effort_mins,due_date,energy,context,source,next_step,scheduled_date,scheduled_start,scheduled_end,last_updated,notes",
                "T001,,Write tests,work,queued,P1,30,2026-04-10,high,,manual,,,,,2026-04-06,",
            ],
        )
        errors = validate_csv(p, SCHEMAS["tasks"])
        assert errors == []


def test_valid_habits_csv() -> None:
    """A well-formed habits CSV produces no errors."""
    with tempfile.TemporaryDirectory() as d:
        p = _write_csv(
            Path(d),
            "habits.csv",
            [
                "habit_id,area,name,frequency,target_per_week,min_value,unit,active,notes,last_updated",
                "H001,health,Exercise,daily,5,30,minutes,true,,2026-04-06",
            ],
        )
        errors = validate_csv(p, SCHEMAS["habits"])
        assert errors == []


def test_valid_goals_csv() -> None:
    """A well-formed goals CSV produces no errors."""
    with tempfile.TemporaryDirectory() as d:
        p = _write_csv(
            Path(d),
            "goals.csv",
            [
                "goal_id,area,title,horizon,target_date,metric_name,metric_target,metric_current,status,last_updated,notes",
                "G001,career,Get promoted,quarter,2026-06-30,level,5,3,active,2026-04-06,",
            ],
        )
        errors = validate_csv(p, SCHEMAS["goals"])
        assert errors == []


# ---------------------------------------------------------------------------
# Missing required field
# ---------------------------------------------------------------------------


def test_missing_required_field_fails() -> None:
    """Empty required field is flagged."""
    with tempfile.TemporaryDirectory() as d:
        p = _write_csv(
            Path(d),
            "tasks.csv",
            [
                "task_id,project_id,title,domain,status,priority,effort_mins,due_date,energy,context,source,next_step,scheduled_date,scheduled_start,scheduled_end,last_updated,notes",
                "T001,,,,queued,P1,30,2026-04-10,high,,manual,,,,,2026-04-06,",
            ],
        )
        errors = validate_csv(p, SCHEMAS["tasks"])
        assert any("title" in e and "required" in e for e in errors)


# ---------------------------------------------------------------------------
# Invalid enum value
# ---------------------------------------------------------------------------


def test_invalid_enum_value_fails() -> None:
    """An enum value not in the allowed list is flagged."""
    with tempfile.TemporaryDirectory() as d:
        p = _write_csv(
            Path(d),
            "tasks.csv",
            [
                "task_id,project_id,title,domain,status,priority,effort_mins,due_date,energy,context,source,next_step,scheduled_date,scheduled_start,scheduled_end,last_updated,notes",
                "T001,,Write tests,work,invalid_status,P1,30,2026-04-10,high,,manual,,,,,2026-04-06,",
            ],
        )
        errors = validate_csv(p, SCHEMAS["tasks"])
        assert any("invalid_status" in e for e in errors)


def test_invalid_priority_enum_fails() -> None:
    """Priority must be a valid enum value (P1, P2, P3)."""
    with tempfile.TemporaryDirectory() as d:
        p = _write_csv(
            Path(d),
            "tasks.csv",
            [
                "task_id,project_id,title,domain,status,priority,effort_mins,due_date,energy,context,source,next_step,scheduled_date,scheduled_start,scheduled_end,last_updated,notes",
                "T001,,Write tests,work,queued,abc,30,2026-04-10,high,,manual,,,,,2026-04-06,",
            ],
        )
        errors = validate_csv(p, SCHEMAS["tasks"])
        assert any("abc" in e for e in errors)


# ---------------------------------------------------------------------------
# Duplicate ID
# ---------------------------------------------------------------------------


def test_duplicate_id_fails() -> None:
    """Duplicate IDs in the id_column are flagged."""
    with tempfile.TemporaryDirectory() as d:
        p = _write_csv(
            Path(d),
            "habits.csv",
            [
                "habit_id,area,name,frequency,target_per_week,min_value,unit,active,notes,last_updated",
                "H001,health,Exercise,daily,5,30,minutes,true,,2026-04-06",
                "H001,health,Meditate,daily,7,10,minutes,true,,2026-04-06",
            ],
        )
        errors = validate_csv(p, SCHEMAS["habits"])
        assert any("duplicate" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# Invalid date format
# ---------------------------------------------------------------------------


def test_invalid_date_format_fails() -> None:
    """A date not in YYYY-MM-DD format is flagged."""
    with tempfile.TemporaryDirectory() as d:
        p = _write_csv(
            Path(d),
            "tasks.csv",
            [
                "task_id,project_id,title,domain,status,priority,effort_mins,due_date,energy,context,source,next_step,scheduled_date,scheduled_start,scheduled_end,last_updated,notes",
                "T001,,Write tests,work,queued,P1,30,04/10/2026,high,,manual,,,,,2026-04-06,",
            ],
        )
        errors = validate_csv(p, SCHEMAS["tasks"])
        assert any("date" in e.lower() and "04/10/2026" in e for e in errors)


# ---------------------------------------------------------------------------
# Nullable field accepts empty
# ---------------------------------------------------------------------------


def test_nullable_field_accepts_empty() -> None:
    """Nullable fields should not flag empty values."""
    with tempfile.TemporaryDirectory() as d:
        p = _write_csv(
            Path(d),
            "tasks.csv",
            [
                "task_id,project_id,title,domain,status,priority,effort_mins,due_date,energy,context,source,next_step,scheduled_date,scheduled_start,scheduled_end,last_updated,notes",
                "T001,,Write tests,work,queued,,,,,,,,,,,,",
            ],
        )
        errors = validate_csv(p, SCHEMAS["tasks"])
        # priority, due_date, energy etc. are nullable — no errors for them
        assert errors == []


# ---------------------------------------------------------------------------
# Invalid numeric types
# ---------------------------------------------------------------------------


def test_invalid_int_field_fails() -> None:
    """Non-integer in an int column is flagged."""
    with tempfile.TemporaryDirectory() as d:
        p = _write_csv(
            Path(d),
            "tasks.csv",
            [
                "task_id,project_id,title,domain,status,priority,effort_mins,due_date,energy,context,source,next_step,scheduled_date,scheduled_start,scheduled_end,last_updated,notes",
                "T001,,Write tests,work,queued,P1,abc,2026-04-10,high,,manual,,,,,2026-04-06,",
            ],
        )
        errors = validate_csv(p, SCHEMAS["tasks"])
        assert any("integer" in e.lower() and "abc" in e for e in errors)


def test_invalid_float_field_fails() -> None:
    """Non-float in a float column is flagged."""
    with tempfile.TemporaryDirectory() as d:
        p = _write_csv(
            Path(d),
            "goals.csv",
            [
                "goal_id,area,title,horizon,target_date,metric_name,metric_target,metric_current,status,last_updated,notes",
                "G001,career,Get promoted,quarter,2026-06-30,level,not_a_num,3,active,2026-04-06,",
            ],
        )
        errors = validate_csv(p, SCHEMAS["goals"])
        assert any("float" in e.lower() and "not_a_num" in e for e in errors)


# ---------------------------------------------------------------------------
# Invalid boolean
# ---------------------------------------------------------------------------


def test_invalid_bool_field_fails() -> None:
    """Non-boolean in a bool column is flagged."""
    with tempfile.TemporaryDirectory() as d:
        p = _write_csv(
            Path(d),
            "habits.csv",
            [
                "habit_id,area,name,frequency,target_per_week,min_value,unit,active,notes,last_updated",
                "H001,health,Exercise,daily,5,30,minutes,maybe,,2026-04-06",
            ],
        )
        errors = validate_csv(p, SCHEMAS["habits"])
        assert any("boolean" in e.lower() and "maybe" in e for e in errors)


# ---------------------------------------------------------------------------
# Header mismatch
# ---------------------------------------------------------------------------


def test_header_mismatch_fails() -> None:
    """Wrong headers produce a header mismatch error."""
    with tempfile.TemporaryDirectory() as d:
        p = _write_csv(
            Path(d),
            "habits.csv",
            [
                "id,name,frequency",
                "H001,Exercise,daily",
            ],
        )
        errors = validate_csv(p, SCHEMAS["habits"])
        assert any("header" in e.lower() or "mismatch" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# File-not-found and empty file
# ---------------------------------------------------------------------------


def test_file_not_found() -> None:
    """Missing file returns an error."""
    errors = validate_csv(Path("/nonexistent/file.csv"), SCHEMAS["tasks"])
    assert any("not found" in e.lower() for e in errors)


def test_empty_file() -> None:
    """Empty file returns an error."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "tasks.csv"
        p.write_text("", encoding="utf-8")
        errors = validate_csv(p, SCHEMAS["tasks"])
        assert any("empty" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# Column count mismatch
# ---------------------------------------------------------------------------


def test_row_column_count_mismatch() -> None:
    """Row with wrong number of columns is flagged."""
    with tempfile.TemporaryDirectory() as d:
        p = _write_csv(
            Path(d),
            "habits.csv",
            [
                "habit_id,area,name,frequency,target_per_week,min_value,unit,active,notes,last_updated",
                "H001,health,Exercise",
            ],
        )
        errors = validate_csv(p, SCHEMAS["habits"])
        assert any("column" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# validate_all
# ---------------------------------------------------------------------------


def test_header_order_mismatch() -> None:
    """Correct columns in wrong order produce order-differs error."""
    with tempfile.TemporaryDirectory() as d:
        # Swap 'area' and 'name' in habits header
        p = _write_csv(
            Path(d),
            "habits.csv",
            [
                "habit_id,name,area,frequency,target_per_week,min_value,unit,active,notes,last_updated",
                "H001,Exercise,health,daily,5,30,minutes,true,,2026-04-06",
            ],
        )
        errors = validate_csv(p, SCHEMAS["habits"])
        assert any("order" in e.lower() for e in errors)


def test_unicode_decode_error() -> None:
    """Binary file triggers encoding error."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "bad.csv"
        p.write_bytes(b"\xff\xfe" + b"\x80" * 200)
        errors = validate_csv(p, SCHEMAS["tasks"])
        assert any("encoding" in e.lower() for e in errors)


def test_csv_parse_error() -> None:
    """CSV parsing error is caught and reported."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "bad.csv"
        header = ",".join(SCHEMAS["tasks"].column_names)
        p.write_text(header + "\n" + "x" * 200 + ",y\n", encoding="utf-8")
        import csv as _csv

        old_limit = _csv.field_size_limit()
        _csv.field_size_limit(10)
        try:
            errors = validate_csv(p, SCHEMAS["tasks"])
            assert any("csv parsing error" in e.lower() for e in errors)
        finally:
            _csv.field_size_limit(old_limit)


def test_validate_all_runs_on_canonical_dir() -> None:
    """validate_all returns a dict with keys for each schema."""
    with tempfile.TemporaryDirectory() as d:
        canonical = Path(d)
        # Create minimal valid files for each schema
        for name, schema in SCHEMAS.items():
            header = ",".join(schema.column_names)
            (canonical / f"{name}.csv").write_text(header + "\n", encoding="utf-8")

        results = validate_all(canonical)
        assert set(results.keys()) == set(SCHEMAS.keys())
        # Header-only files should pass (no data rows to fail)
        for name, errs in results.items():
            assert errs == [], f"{name} had errors: {errs}"
