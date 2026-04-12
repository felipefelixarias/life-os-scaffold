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
ForeignKey = csv_schemas.ForeignKey
SCHEMAS = csv_schemas.SCHEMAS
FOREIGN_KEYS = csv_schemas.FOREIGN_KEYS
validate_csv = csv_schemas.validate_csv
validate_all = csv_schemas.validate_all
get_time_fields = csv_schemas.get_time_fields
get_numeric_constraints = csv_schemas.get_numeric_constraints
get_foreign_keys = csv_schemas.get_foreign_keys


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


# ---------------------------------------------------------------------------
# Time validation
# ---------------------------------------------------------------------------


def test_valid_time_field() -> None:
    """Valid HH:MM times produce no errors."""
    with tempfile.TemporaryDirectory() as d:
        p = _write_csv(
            Path(d),
            "time_blocks.csv",
            [
                "block_id,date,start,end,title,domain,task_id,source,status,notes",
                "B001,2026-04-10,09:00,10:30,Focus,work,,manual,planned,",
            ],
        )
        errors = validate_csv(p, SCHEMAS["time_blocks"])
        assert errors == []


def test_invalid_time_field_fails() -> None:
    """Non-HH:MM time is flagged."""
    with tempfile.TemporaryDirectory() as d:
        p = _write_csv(
            Path(d),
            "time_blocks.csv",
            [
                "block_id,date,start,end,title,domain,task_id,source,status,notes",
                "B001,2026-04-10,9am,10am,Focus,work,,manual,planned,",
            ],
        )
        errors = validate_csv(p, SCHEMAS["time_blocks"])
        assert any("time" in e.lower() and "9am" in e for e in errors)


def test_nullable_time_field_accepts_empty() -> None:
    """Nullable time fields accept empty values without error."""
    with tempfile.TemporaryDirectory() as d:
        p = _write_csv(
            Path(d),
            "time_logs.csv",
            [
                "log_id,date,activity,domain,duration_mins,start_time,end_time,notes,last_updated",
                "L001,2026-04-10,Coding,work,60,,,,",
            ],
        )
        errors = validate_csv(p, SCHEMAS["time_logs"])
        assert errors == []


def test_get_time_fields_returns_time_columns() -> None:
    """get_time_fields returns time-typed columns for schemas that have them."""
    result = get_time_fields()
    assert "time_blocks.csv" in result
    assert "start" in result["time_blocks.csv"]
    assert "end" in result["time_blocks.csv"]
    assert "calendar_events.csv" in result
    assert "start_time" in result["calendar_events.csv"]


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


# ---------------------------------------------------------------------------
# Numeric range validation
# ---------------------------------------------------------------------------


def test_int_below_minimum_fails() -> None:
    """Integer value below min_value is flagged."""
    with tempfile.TemporaryDirectory() as d:
        p = _write_csv(
            Path(d),
            "tasks.csv",
            [
                "task_id,project_id,title,domain,status,priority,effort_mins,due_date,energy,context,source,next_step,scheduled_date,scheduled_start,scheduled_end,last_updated,notes",
                "T001,,Write tests,work,queued,P1,0,2026-04-10,high,,manual,,,,,2026-04-06,",
            ],
        )
        errors = validate_csv(p, SCHEMAS["tasks"])
        assert any("below minimum" in e for e in errors)


def test_int_above_maximum_fails() -> None:
    """Integer value above max_value is flagged."""
    with tempfile.TemporaryDirectory() as d:
        p = _write_csv(
            Path(d),
            "tasks.csv",
            [
                "task_id,project_id,title,domain,status,priority,effort_mins,due_date,energy,context,source,next_step,scheduled_date,scheduled_start,scheduled_end,last_updated,notes",
                "T001,,Write tests,work,queued,P1,999,2026-04-10,high,,manual,,,,,2026-04-06,",
            ],
        )
        errors = validate_csv(p, SCHEMAS["tasks"])
        assert any("exceeds maximum" in e for e in errors)


def test_float_below_minimum_fails() -> None:
    """Float value below min_value is flagged."""
    with tempfile.TemporaryDirectory() as d:
        p = _write_csv(
            Path(d),
            "goals.csv",
            [
                "goal_id,area,title,horizon,target_date,metric_name,metric_target,metric_current,status,last_updated,notes",
                "G001,career,Get promoted,quarter,2026-06-30,level,-5,3,active,2026-04-06,",
            ],
        )
        errors = validate_csv(p, SCHEMAS["goals"])
        assert any("below minimum" in e for e in errors)


def test_float_above_maximum_fails() -> None:
    """Float value above max_value is flagged (using habits min_value col with max constraint)."""
    # Create a custom schema to test float max
    schema = CSVSchema(
        name="test",
        columns=[
            ColumnSchema("id", required=True),
            ColumnSchema(
                "score", dtype="float", nullable=True, min_value=0, max_value=100
            ),
        ],
    )
    with tempfile.TemporaryDirectory() as d:
        p = _write_csv(Path(d), "test.csv", ["id,score", "1,200.5"])
        errors = validate_csv(p, schema)
        assert any("exceeds maximum" in e for e in errors)


# ---------------------------------------------------------------------------
# Time format validation
# ---------------------------------------------------------------------------


def test_valid_time_format_passes() -> None:
    """Valid HH:MM time values pass validation."""
    with tempfile.TemporaryDirectory() as d:
        p = _write_csv(
            Path(d),
            "time_blocks.csv",
            [
                "block_id,date,start,end,title,domain,task_id,source,status,notes",
                "B001,2026-04-10,09:00,10:30,Focus work,,,,planned,",
            ],
        )
        errors = validate_csv(p, SCHEMAS["time_blocks"])
        assert errors == []


def test_invalid_time_format_fails() -> None:
    """Invalid time format is flagged."""
    with tempfile.TemporaryDirectory() as d:
        p = _write_csv(
            Path(d),
            "time_blocks.csv",
            [
                "block_id,date,start,end,title,domain,task_id,source,status,notes",
                "B001,2026-04-10,25:00,10:30,Focus work,,,,planned,",
            ],
        )
        errors = validate_csv(p, SCHEMAS["time_blocks"])
        assert any("time" in e.lower() and "25:00" in e for e in errors)


# ---------------------------------------------------------------------------
# Accessor functions for new schema properties
# ---------------------------------------------------------------------------


def test_get_time_fields() -> None:
    """get_time_fields returns time columns grouped by file."""
    result = get_time_fields()
    assert "time_blocks.csv" in result
    assert "start" in result["time_blocks.csv"]
    assert "end" in result["time_blocks.csv"]
    assert "calendar_events.csv" in result
    assert "start_time" in result["calendar_events.csv"]


def test_get_numeric_constraints() -> None:
    """get_numeric_constraints returns range constraints from schema."""
    result = get_numeric_constraints()
    assert "tasks.csv" in result
    assert "effort_mins" in result["tasks.csv"]
    assert result["tasks.csv"]["effort_mins"]["min"] == 1
    assert result["tasks.csv"]["effort_mins"]["max"] == 480
    assert result["tasks.csv"]["effort_mins"]["type"] == "int"


# ---------------------------------------------------------------------------
# Foreign key schema definitions
# ---------------------------------------------------------------------------


def test_foreign_keys_defined() -> None:
    """All expected FK relationships are defined."""
    fks = get_foreign_keys()
    assert len(fks) >= 3
    sources = {(fk.source_file, fk.source_column) for fk in fks}
    assert ("tasks", "project_id") in sources
    assert ("time_blocks", "task_id") in sources
    assert ("daily_log", "habit_id") in sources


def test_foreign_key_targets_reference_valid_schemas() -> None:
    """Every FK target_file and target_column must exist in SCHEMAS."""
    for fk in FOREIGN_KEYS:
        assert fk.target_file in SCHEMAS, (
            f"target_file '{fk.target_file}' not in SCHEMAS"
        )
        schema = SCHEMAS[fk.target_file]
        assert fk.target_column in schema.column_names, (
            f"target_column '{fk.target_column}' not in {fk.target_file} schema"
        )


def test_foreign_key_sources_reference_valid_columns() -> None:
    """Every FK source_column must exist in the source schema (SCHEMAS or LOG_SCHEMAS)."""
    all_schemas = csv_schemas.ALL_SCHEMAS
    for fk in FOREIGN_KEYS:
        assert fk.source_file in all_schemas, (
            f"source_file '{fk.source_file}' not in any schema"
        )
        schema = all_schemas[fk.source_file]
        assert fk.source_column in schema.column_names, (
            f"source_column '{fk.source_column}' not in {fk.source_file} schema"
        )


def test_foreign_key_dataclass_fields() -> None:
    """ForeignKey dataclass has the expected fields and defaults."""
    fk = ForeignKey(
        source_file="tasks",
        source_column="project_id",
        target_file="projects",
        target_column="project_id",
    )
    assert fk.location == "canonical"  # default

    fk_log = ForeignKey(
        source_file="daily_log",
        source_column="habit_id",
        target_file="habits",
        target_column="habit_id",
        location="logs",
    )
    assert fk_log.location == "logs"


def test_get_foreign_keys_returns_copy() -> None:
    """get_foreign_keys returns a new list, not the internal reference."""
    fks1 = get_foreign_keys()
    fks2 = get_foreign_keys()
    assert fks1 is not fks2
    assert fks1 == fks2
