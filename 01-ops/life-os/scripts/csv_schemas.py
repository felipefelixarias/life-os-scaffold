"""CSV schema definitions and validation for all canonical data files."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from datetime import datetime
from functools import cached_property
from pathlib import Path


@dataclass
class ColumnSchema:
    """Schema definition for a single CSV column."""

    name: str
    required: bool = True
    dtype: str = "str"  # str, int, float, date, time, bool, enum
    enum_values: list[str] = field(default_factory=list)
    nullable: bool = False
    min_value: int | float | None = None
    max_value: int | float | None = None


@dataclass
class CSVSchema:
    """Schema definition for a CSV file."""

    name: str
    columns: list[ColumnSchema]
    id_column: str | None = None

    @property
    def column_names(self) -> list[str]:
        """Return list of column names in order."""
        return [col.name for col in self.columns]

    @cached_property
    def column_map(self) -> dict[str, ColumnSchema]:
        """Return a cached name→ColumnSchema mapping for O(1) lookups."""
        return {col.name: col for col in self.columns}

    def get_column(self, name: str) -> ColumnSchema | None:
        """Look up a column schema by name."""
        return self.column_map.get(name)


LOG_SCHEMAS: dict[str, CSVSchema] = {
    "daily_log": CSVSchema(
        name="daily_log",
        columns=[
            ColumnSchema("date", required=True, dtype="date"),
            ColumnSchema("habit_id", required=True),
            ColumnSchema("value", required=True),
            ColumnSchema("notes", nullable=True),
        ],
    ),
    "activity_log": CSVSchema(
        name="activity_log",
        columns=[
            ColumnSchema("timestamp", required=True),
            ColumnSchema("event", required=True),
            ColumnSchema("details", nullable=True),
        ],
    ),
}

SCHEMAS: dict[str, CSVSchema] = {
    "tasks": CSVSchema(
        name="tasks",
        id_column="task_id",
        columns=[
            ColumnSchema("task_id", required=True),
            ColumnSchema("project_id", nullable=True),
            ColumnSchema("title", required=True),
            ColumnSchema("domain", nullable=True),
            ColumnSchema(
                "status",
                dtype="enum",
                enum_values=[
                    "queued",
                    "in_progress",
                    "blocked",
                    "completed",
                    "done",
                    "dropped",
                ],
                nullable=True,
            ),
            ColumnSchema(
                "priority",
                dtype="enum",
                enum_values=["P1", "P2", "P3"],
                nullable=True,
            ),
            ColumnSchema(
                "effort_mins", dtype="int", nullable=True, min_value=1, max_value=480
            ),
            ColumnSchema("due_date", dtype="date", nullable=True),
            ColumnSchema(
                "energy",
                dtype="enum",
                enum_values=["low", "medium", "high"],
                nullable=True,
            ),
            ColumnSchema("context", nullable=True),
            ColumnSchema(
                "source",
                dtype="enum",
                enum_values=["manual", "auto", "imported"],
                nullable=True,
            ),
            ColumnSchema("next_step", nullable=True),
            ColumnSchema("scheduled_date", dtype="date", nullable=True),
            ColumnSchema("scheduled_start", dtype="time", nullable=True),
            ColumnSchema("scheduled_end", dtype="time", nullable=True),
            ColumnSchema("last_updated", dtype="date", nullable=True),
            ColumnSchema("notes", nullable=True),
        ],
    ),
    "habits": CSVSchema(
        name="habits",
        id_column="habit_id",
        columns=[
            ColumnSchema("habit_id", required=True),
            ColumnSchema("area", required=True),
            ColumnSchema("name", required=True),
            ColumnSchema(
                "frequency",
                required=True,
                dtype="enum",
                enum_values=["daily", "weekly"],
            ),
            ColumnSchema(
                "target_per_week", dtype="int", nullable=True, min_value=1, max_value=7
            ),
            ColumnSchema("min_value", dtype="float", nullable=True, min_value=0),
            ColumnSchema("unit", nullable=True),
            ColumnSchema("active", dtype="bool", nullable=True),
            ColumnSchema("notes", nullable=True),
            ColumnSchema("last_updated", dtype="date", nullable=True),
        ],
    ),
    "goals": CSVSchema(
        name="goals",
        id_column="goal_id",
        columns=[
            ColumnSchema("goal_id", required=True),
            ColumnSchema("area", required=True),
            ColumnSchema("title", required=True),
            ColumnSchema(
                "horizon",
                dtype="enum",
                enum_values=["quarter", "year", "month"],
                nullable=True,
            ),
            ColumnSchema("target_date", dtype="date", nullable=True),
            ColumnSchema("metric_name", nullable=True),
            ColumnSchema("metric_target", dtype="float", nullable=True, min_value=0),
            ColumnSchema("metric_current", dtype="float", nullable=True, min_value=0),
            ColumnSchema(
                "status",
                dtype="enum",
                enum_values=["active", "completed", "paused", "dropped"],
                nullable=True,
            ),
            ColumnSchema("last_updated", dtype="date", nullable=True),
            ColumnSchema("notes", nullable=True),
        ],
    ),
    "projects": CSVSchema(
        name="projects",
        id_column="project_id",
        columns=[
            ColumnSchema("project_id", required=True),
            ColumnSchema("area", required=True),
            ColumnSchema("name", required=True),
            ColumnSchema(
                "status",
                dtype="enum",
                enum_values=["planning", "active", "paused", "completed"],
                nullable=True,
            ),
            ColumnSchema("start_date", dtype="date", nullable=True),
            ColumnSchema("target_date", dtype="date", nullable=True),
            ColumnSchema("description", nullable=True),
            ColumnSchema("last_updated", dtype="date", nullable=True),
            ColumnSchema("notes", nullable=True),
            ColumnSchema("active", dtype="bool", nullable=True),
        ],
    ),
    "calendar_events": CSVSchema(
        name="calendar_events",
        id_column="event_id",
        columns=[
            ColumnSchema("event_id", required=True),
            ColumnSchema("date", required=True, dtype="date"),
            ColumnSchema("start_time", required=True, dtype="time"),
            ColumnSchema("end_time", required=True, dtype="time"),
            ColumnSchema("title", required=True),
            ColumnSchema("location", nullable=True),
            ColumnSchema("attendees", nullable=True),
            ColumnSchema(
                "source",
                dtype="enum",
                enum_values=["google_calendar", "manual", "outlook"],
                nullable=True,
            ),
            ColumnSchema("calendar", nullable=True),
            ColumnSchema("notes", nullable=True),
        ],
    ),
    "time_blocks": CSVSchema(
        name="time_blocks",
        id_column="block_id",
        columns=[
            ColumnSchema("block_id", required=True),
            ColumnSchema("date", required=True, dtype="date"),
            ColumnSchema("start", required=True, dtype="time"),
            ColumnSchema("end", required=True, dtype="time"),
            ColumnSchema("title", required=True),
            ColumnSchema("domain", nullable=True),
            ColumnSchema("task_id", nullable=True),
            ColumnSchema(
                "source",
                dtype="enum",
                enum_values=["manual", "auto_planner", "imported"],
                nullable=True,
            ),
            ColumnSchema(
                "status",
                dtype="enum",
                enum_values=["planned", "in_progress", "completed", "skipped"],
                nullable=True,
            ),
            ColumnSchema("notes", nullable=True),
        ],
    ),
    "time_logs": CSVSchema(
        name="time_logs",
        id_column="log_id",
        columns=[
            ColumnSchema("log_id", required=True),
            ColumnSchema("date", required=True, dtype="date"),
            ColumnSchema("activity", required=True),
            ColumnSchema("domain", nullable=True),
            ColumnSchema(
                "duration_mins", dtype="int", nullable=True, min_value=1, max_value=1440
            ),
            ColumnSchema("start_time", dtype="time", nullable=True),
            ColumnSchema("end_time", dtype="time", nullable=True),
            ColumnSchema("notes", nullable=True),
            ColumnSchema("last_updated", dtype="date", nullable=True),
        ],
    ),
}


def _validate_value(value: str, col: ColumnSchema, row_num: int) -> list[str]:
    """Validate a single cell value against its column schema."""
    errors: list[str] = []
    stripped = value.strip()

    # Check required / nullable
    if not stripped:
        if col.required and not col.nullable:
            errors.append(f"Row {row_num}: required field '{col.name}' is empty")
        return errors  # nothing more to check on empty

    # Type checks
    if col.dtype == "enum":
        if stripped not in col.enum_values:
            errors.append(
                f"Row {row_num}: invalid value '{stripped}' for '{col.name}', "
                f"expected one of {col.enum_values}"
            )

    elif col.dtype == "int":
        try:
            num = int(stripped)
        except ValueError:
            errors.append(
                f"Row {row_num}: '{stripped}' is not a valid integer for '{col.name}'"
            )
        else:
            if col.min_value is not None and num < col.min_value:
                errors.append(
                    f"Row {row_num}: {col.name} value {num} is below minimum {col.min_value}"
                )
            if col.max_value is not None and num > col.max_value:
                errors.append(
                    f"Row {row_num}: {col.name} value {num} exceeds maximum {col.max_value}"
                )

    elif col.dtype == "float":
        try:
            num_f = float(stripped)
        except ValueError:
            errors.append(
                f"Row {row_num}: '{stripped}' is not a valid float for '{col.name}'"
            )
        else:
            if col.min_value is not None and num_f < col.min_value:
                errors.append(
                    f"Row {row_num}: {col.name} value {num_f} is below minimum {col.min_value}"
                )
            if col.max_value is not None and num_f > col.max_value:
                errors.append(
                    f"Row {row_num}: {col.name} value {num_f} exceeds maximum {col.max_value}"
                )

    elif col.dtype == "date":
        try:
            datetime.strptime(stripped, "%Y-%m-%d")
        except ValueError:
            errors.append(
                f"Row {row_num}: '{stripped}' is not a valid date (YYYY-MM-DD) for '{col.name}'"
            )

    elif col.dtype == "time":
        if not re.match(r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$", stripped):
            errors.append(
                f"Row {row_num}: '{stripped}' is not a valid time (HH:MM) for '{col.name}'"
            )

    elif col.dtype == "bool" and stripped.lower() not in (
        "true",
        "false",
        "1",
        "0",
        "yes",
        "no",
    ):
        errors.append(
            f"Row {row_num}: '{stripped}' is not a valid boolean for '{col.name}'"
        )

    return errors


def validate_csv(filepath: Path, schema: CSVSchema) -> list[str]:
    """Validate a CSV file against its schema. Returns list of errors."""
    errors: list[str] = []

    if not filepath.exists():
        errors.append(f"File not found: {filepath}")
        return errors

    try:
        with filepath.open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)

            if header is None:
                errors.append("File is empty (no header row)")
                return errors

            # Validate headers
            expected = schema.column_names
            if header != expected:
                missing = set(expected) - set(header)
                extra = set(header) - set(expected)
                parts = [f"Header mismatch for '{schema.name}'"]
                if missing:
                    parts.append(f"missing columns: {sorted(missing)}")
                if extra:
                    parts.append(f"unexpected columns: {sorted(extra)}")
                if not missing and not extra:
                    parts.append(
                        f"column order differs: got {header}, expected {expected}"
                    )
                errors.append("; ".join(parts))
                # If columns don't match at all, we can't reliably validate rows
                if missing:
                    return errors

            # Build column lookup from actual header
            col_lookup: dict[str, ColumnSchema] = {}
            for h in header:
                col = schema.get_column(h)
                if col is not None:
                    col_lookup[h] = col

            seen_ids: set[str] = set()

            for row_num, row in enumerate(reader, start=2):
                if len(row) != len(header):
                    errors.append(
                        f"Row {row_num}: expected {len(header)} columns, got {len(row)}"
                    )
                    continue

                row_data = dict(zip(header, row, strict=False))

                # Per-field validation
                for h, val in row_data.items():
                    col = col_lookup.get(h)
                    if col is not None:
                        errors.extend(_validate_value(val, col, row_num))

                # Unique ID check
                if schema.id_column and schema.id_column in row_data:
                    id_val = row_data[schema.id_column].strip()
                    if id_val:
                        if id_val in seen_ids:
                            errors.append(
                                f"Row {row_num}: duplicate {schema.id_column} '{id_val}'"
                            )
                        seen_ids.add(id_val)

    except UnicodeDecodeError as e:
        errors.append(f"Encoding error: {e}")
    except csv.Error as e:
        errors.append(f"CSV parsing error: {e}")

    return errors


ALL_SCHEMAS: dict[str, CSVSchema] = {**SCHEMAS, **LOG_SCHEMAS}


def get_expected_headers() -> dict[str, list[str]]:
    """Return {filename: [column_names]} for all schemas (keyed by 'name.csv')."""
    return {f"{name}.csv": schema.column_names for name, schema in ALL_SCHEMAS.items()}


def get_required_fields() -> dict[str, set[str]]:
    """Return {filename: {required_column_names}} for all schemas."""
    return {
        f"{name}.csv": {
            col.name for col in schema.columns if col.required and not col.nullable
        }
        for name, schema in ALL_SCHEMAS.items()
    }


def get_enum_fields() -> dict[str, dict[str, list[str]]]:
    """Return {filename: {column: [allowed_values]}} for enum and bool columns.

    Bool columns are included as ["true", "false"] so that integrity validators
    can reject values like "maybe" without special-casing.
    """
    result: dict[str, dict[str, list[str]]] = {}
    for name, schema in ALL_SCHEMAS.items():
        enums: dict[str, list[str]] = {}
        for col in schema.columns:
            if col.dtype == "enum" and col.enum_values:
                enums[col.name] = col.enum_values
            elif col.dtype == "bool":
                enums[col.name] = ["true", "false"]
        if enums:
            result[f"{name}.csv"] = enums
    return result


def get_id_fields() -> dict[str, str]:
    """Return {filename: id_column_name} for schemas with an id_column."""
    return {
        f"{name}.csv": schema.id_column
        for name, schema in ALL_SCHEMAS.items()
        if schema.id_column
    }


def get_date_fields() -> dict[str, set[str]]:
    """Return {filename: {date_column_names}} for columns with dtype='date'."""
    result: dict[str, set[str]] = {}
    for name, schema in ALL_SCHEMAS.items():
        dates = {col.name for col in schema.columns if col.dtype == "date"}
        if dates:
            result[f"{name}.csv"] = dates
    return result


def get_time_fields() -> dict[str, set[str]]:
    """Return {filename: {time_column_names}} for columns with dtype='time'."""
    result: dict[str, set[str]] = {}
    for name, schema in ALL_SCHEMAS.items():
        times = {col.name for col in schema.columns if col.dtype == "time"}
        if times:
            result[f"{name}.csv"] = times
    return result


def get_numeric_constraints() -> dict[
    str, dict[str, dict[str, int | float | str | None]]
]:
    """Return {filename: {column: {min, max, type}}} for numeric columns with range constraints."""
    result: dict[str, dict[str, dict[str, int | float | str | None]]] = {}
    for name, schema in ALL_SCHEMAS.items():
        constraints: dict[str, dict[str, int | float | str | None]] = {}
        for col in schema.columns:
            if col.dtype in ("int", "float") and (
                col.min_value is not None or col.max_value is not None
            ):
                constraints[col.name] = {
                    "min": col.min_value,
                    "max": col.max_value,
                    "type": col.dtype,
                }
        if constraints:
            result[f"{name}.csv"] = constraints
    return result


def validate_all(canonical_dir: Path) -> dict[str, list[str]]:
    """Validate all canonical CSV files. Returns dict of schema_name -> errors."""
    results: dict[str, list[str]] = {}
    for name, schema in SCHEMAS.items():
        filepath = canonical_dir / f"{name}.csv"
        results[name] = validate_csv(filepath, schema)
    return results
