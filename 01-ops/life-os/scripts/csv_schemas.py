"""CSV schema definitions and validation for all canonical data files."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class ColumnSchema:
    """Schema definition for a single CSV column."""

    name: str
    required: bool = True
    dtype: str = "str"  # str, int, float, date, bool, enum
    enum_values: list[str] = field(default_factory=list)
    nullable: bool = False


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

    def get_column(self, name: str) -> ColumnSchema | None:
        """Look up a column schema by name."""
        for col in self.columns:
            if col.name == name:
                return col
        return None


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
            ColumnSchema("effort_mins", dtype="int", nullable=True),
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
            ColumnSchema("scheduled_start", nullable=True),
            ColumnSchema("scheduled_end", nullable=True),
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
            ColumnSchema("target_per_week", dtype="int", nullable=True),
            ColumnSchema("min_value", dtype="float", nullable=True),
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
            ColumnSchema("metric_target", dtype="float", nullable=True),
            ColumnSchema("metric_current", dtype="float", nullable=True),
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
            ColumnSchema("start_time", required=True),
            ColumnSchema("end_time", required=True),
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
            ColumnSchema("start", required=True),
            ColumnSchema("end", required=True),
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
            ColumnSchema("duration_mins", dtype="int", nullable=True),
            ColumnSchema("start_time", nullable=True),
            ColumnSchema("end_time", nullable=True),
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
            int(stripped)
        except ValueError:
            errors.append(
                f"Row {row_num}: '{stripped}' is not a valid integer for '{col.name}'"
            )

    elif col.dtype == "float":
        try:
            float(stripped)
        except ValueError:
            errors.append(
                f"Row {row_num}: '{stripped}' is not a valid float for '{col.name}'"
            )

    elif col.dtype == "date":
        try:
            datetime.strptime(stripped, "%Y-%m-%d")
        except ValueError:
            errors.append(
                f"Row {row_num}: '{stripped}' is not a valid date (YYYY-MM-DD) for '{col.name}'"
            )

    elif col.dtype == "bool":
        if stripped.lower() not in ("true", "false", "1", "0", "yes", "no"):
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
                    parts.append(f"column order differs: got {header}, expected {expected}")
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

                row_data = dict(zip(header, row))

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


def validate_all(canonical_dir: Path) -> dict[str, list[str]]:
    """Validate all canonical CSV files. Returns dict of schema_name -> errors."""
    results: dict[str, list[str]] = {}
    for name, schema in SCHEMAS.items():
        filepath = canonical_dir / f"{name}.csv"
        results[name] = validate_csv(filepath, schema)
    return results
