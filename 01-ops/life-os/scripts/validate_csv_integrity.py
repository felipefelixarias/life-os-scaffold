#!/usr/bin/env python3
"""Comprehensive CSV data validation for life-os scaffold."""

from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path
from typing import cast

# Paths relative to repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
CANONICAL_DIR = REPO_ROOT / "01-ops" / "life-os" / "data" / "canonical"
LOGS_DIR = REPO_ROOT / "01-ops" / "life-os" / "logs"

# Expected schemas based on docs/csv-schemas.md
EXPECTED_SCHEMAS = {
    "habits.csv": [
        "habit_id", "area", "name", "frequency", "target_per_week",
        "min_value", "unit", "active", "notes", "last_updated"
    ],
    "goals.csv": [
        "goal_id", "area", "title", "horizon", "target_date", "metric_name",
        "metric_target", "metric_current", "status", "last_updated", "notes"
    ],
    "tasks.csv": [
        "task_id", "title", "domain", "project_id", "status", "priority",
        "effort_mins", "due_date", "energy", "context", "source", "next_step",
        "scheduled_date", "scheduled_start", "scheduled_end", "last_updated", "notes"
    ],
    "projects.csv": [
        "project_id", "area", "name", "status", "start_date", "target_date",
        "description", "last_updated", "notes", "active"
    ],
    "time_blocks.csv": [
        "block_id", "date", "start", "end", "title", "domain",
        "task_id", "source", "status", "notes"
    ],
    "time_logs.csv": [
        "log_id", "date", "start_time", "end_time", "activity", "domain",
        "duration_mins", "task_id", "notes"
    ],
    "calendar_events.csv": [
        "event_id", "date", "start_time", "end_time", "title",
        "location", "attendees", "source", "calendar", "notes"
    ],
    "daily_log.csv": [
        "date", "habit_id", "value", "notes"
    ],
    "activity_log.csv": [
        "timestamp", "activity", "notes"
    ]
}

# Required fields that cannot be empty
REQUIRED_FIELDS = {
    "habits.csv": {"habit_id", "area", "name", "frequency", "target_per_week", "min_value", "unit", "active"},
    "goals.csv": {"goal_id", "area", "title"},
    "tasks.csv": {"task_id", "title", "domain"},
    "projects.csv": {"project_id", "area", "name"},
    "time_blocks.csv": {"block_id", "date", "start", "end", "title"},
    "time_logs.csv": {"log_id", "date", "activity", "start_time", "end_time"},
    "calendar_events.csv": {"event_id", "date", "start_time", "end_time", "title"},
    "daily_log.csv": {"date", "habit_id", "value"},
    "activity_log.csv": {"timestamp", "activity"}
}

# Enum validation
ENUM_FIELDS = {
    "habits.csv": {"frequency": ["daily", "weekly"], "active": ["true", "false"]},
    "goals.csv": {"horizon": ["quarter", "year", "month"], "status": ["active", "completed", "paused", "dropped"]},
    "tasks.csv": {
        "status": ["queued", "in_progress", "blocked", "completed"],
        "priority": ["1", "2", "3", "4", "5"],  # Should be integers as strings
        "energy": ["low", "medium", "high"],
        "source": ["manual", "auto", "imported"]
    },
    "projects.csv": {
        "status": ["planning", "active", "paused", "completed"],
        "active": ["true", "false"]
    },
    "time_blocks.csv": {
        "source": ["manual", "auto_planner", "imported"],
        "status": ["planned", "in_progress", "completed", "skipped"]
    },
    "calendar_events.csv": {
        "source": ["google_calendar", "manual", "outlook"]
    }
}

# Numeric field validation
NUMERIC_FIELDS = {
    "habits.csv": {
        "target_per_week": {"min": 1, "max": 7, "type": "int"},
        "min_value": {"min": 0, "type": "float"}
    },
    "tasks.csv": {
        "priority": {"min": 1, "max": 5, "type": "int"},
        "effort_mins": {"min": 1, "max": 480, "type": "int"}  # Max 8 hours
    },
    "goals.csv": {
        "metric_target": {"min": 0, "type": "float"},
        "metric_current": {"min": 0, "type": "float"}
    },
    "time_logs.csv": {
        "duration_mins": {"min": 1, "max": 1440, "type": "int"}  # Max 24 hours
    }
}

# Time range validation (start must be before end)
TIME_RANGE_FIELDS = {
    "time_blocks.csv": {"start": "start", "end": "end"},
    "time_logs.csv": {"start": "start_time", "end": "end_time"},
    "calendar_events.csv": {"start": "start_time", "end": "end_time"},
    "tasks.csv": {"start": "scheduled_start", "end": "scheduled_end"}
}

# Duration consistency validation
DURATION_CONSISTENCY_FIELDS = {
    "time_logs.csv": {
        "start_time": "start_time",
        "end_time": "end_time",
        "duration": "duration_mins"
    }
}

# Date range validation (start must be before end)
DATE_RANGE_FIELDS = {
    "projects.csv": {"start": "start_date", "end": "target_date"},
    "tasks.csv": {"start": "scheduled_date", "end": "due_date"}
}

# Date and time fields
DATE_FIELDS = {
    "habits.csv": {"last_updated"},
    "goals.csv": {"target_date", "last_updated"},
    "tasks.csv": {"due_date", "scheduled_date", "last_updated"},
    "projects.csv": {"start_date", "target_date", "last_updated"},
    "time_blocks.csv": {"date"},
    "time_logs.csv": {"date"},
    "calendar_events.csv": {"date"},
    "daily_log.csv": {"date"}
}

TIME_FIELDS = {
    "time_blocks.csv": {"start", "end"},
    "time_logs.csv": {"start_time", "end_time"},
    "calendar_events.csv": {"start_time", "end_time"}
}

# ID fields for duplicate checking
ID_FIELDS = {
    "habits.csv": "habit_id",
    "goals.csv": "goal_id",
    "tasks.csv": "task_id",
    "projects.csv": "project_id",
    "time_blocks.csv": "block_id",
    "time_logs.csv": "log_id",
    "calendar_events.csv": "event_id"
}


class ValidationResult:
    """Container for validation results."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.passed = True

    def add_error(self, message: str) -> None:
        """Add an error message."""
        self.errors.append(message)
        self.passed = False

    def add_warning(self, message: str) -> None:
        """Add a warning message."""
        self.warnings.append(message)


def validate_date_format(date_str: str) -> bool:
    """Validate date is in YYYY-MM-DD format."""
    if not date_str.strip():
        return True  # Empty dates are often optional

    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def validate_time_format(time_str: str) -> bool:
    """Validate time is in HH:MM format."""
    if not time_str.strip():
        return True  # Empty times are often optional

    return bool(re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', time_str))


def validate_numeric_field(value_str: str, field_name: str, min_val: int | float | None = None, max_val: int | float | None = None, is_integer: bool = True) -> tuple[bool, str]:
    """
    Validate numeric fields with optional range constraints.

    Args:
        value_str: The string value to validate
        field_name: Name of the field for error messages
        min_val: Minimum allowed value (inclusive)
        max_val: Maximum allowed value (inclusive)
        is_integer: Whether the value should be an integer

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not value_str.strip():
        return True, ""  # Empty values are often optional

    try:
        value = int(value_str) if is_integer else float(value_str)
    except ValueError:
        return False, f"'{value_str}' is not a valid {'integer' if is_integer else 'number'} for {field_name}"

    if min_val is not None and value < min_val:
        return False, f"{field_name} value {value} is below minimum allowed value {min_val}"

    if max_val is not None and value > max_val:
        return False, f"{field_name} value {value} exceeds maximum allowed value {max_val}"

    return True, ""


def validate_time_range(start_time: str, end_time: str) -> tuple[bool, str]:
    """
    Validate that start time is before end time.

    Args:
        start_time: Start time in HH:MM format
        end_time: End time in HH:MM format

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not start_time.strip() or not end_time.strip():
        return True, ""  # Skip validation if either time is empty

    if not (validate_time_format(start_time) and validate_time_format(end_time)):
        return True, ""  # Skip if either time format is invalid (will be caught by format validation)

    try:
        from datetime import datetime
        start_dt = datetime.strptime(start_time, "%H:%M")
        end_dt = datetime.strptime(end_time, "%H:%M")

        if start_dt >= end_dt:
            return False, f"Start time {start_time} must be before end time {end_time}"

    except ValueError:
        return True, ""  # Skip validation if parsing fails

    return True, ""


def validate_duration_consistency(start_time: str, end_time: str, duration_mins: str) -> tuple[bool, str]:
    """
    Validate that duration_mins matches the calculated duration from start to end time.

    Args:
        start_time: Start time in HH:MM format
        end_time: End time in HH:MM format
        duration_mins: Duration in minutes as string

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not all([start_time.strip(), end_time.strip(), duration_mins.strip()]):
        return True, ""  # Skip if any field is empty

    if not (validate_time_format(start_time) and validate_time_format(end_time)):
        return True, ""  # Skip if time formats are invalid

    try:
        duration = int(duration_mins)
    except ValueError:
        return True, ""  # Skip if duration is not a valid integer

    try:
        from datetime import datetime
        start_dt = datetime.strptime(start_time, "%H:%M")
        end_dt = datetime.strptime(end_time, "%H:%M")

        # Handle midnight rollover
        if end_dt <= start_dt:
            from datetime import timedelta
            end_dt += timedelta(days=1)

        calculated_mins = int((end_dt - start_dt).total_seconds() / 60)

        if abs(calculated_mins - duration) > 1:  # Allow 1-minute tolerance for rounding
            return False, f"Duration {duration} minutes doesn't match calculated duration {calculated_mins} minutes (from {start_time} to {end_time})"

    except (ValueError, OverflowError):
        return True, ""  # Skip validation if parsing fails

    return True, ""


def validate_date_range(start_date: str, end_date: str, field_names: tuple[str, str]) -> tuple[bool, str]:
    """
    Validate that start date is before or equal to end date.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        field_names: Tuple of (start_field_name, end_field_name) for error messages

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not start_date.strip() or not end_date.strip():
        return True, ""  # Skip validation if either date is empty

    if not (validate_date_format(start_date) and validate_date_format(end_date)):
        return True, ""  # Skip if either date format is invalid

    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        if start_dt > end_dt:
            return False, f"{field_names[0]} ({start_date}) must be before or equal to {field_names[1]} ({end_date})"

    except ValueError:
        return True, ""  # Skip validation if parsing fails

    return True, ""


def validate_csv_schema(file_path: Path) -> ValidationResult:
    """Validate CSV file schema and data integrity."""
    result = ValidationResult(file_path)
    filename = file_path.name

    if not file_path.exists():
        result.add_error(f"File {filename} does not exist")
        return result

    if filename not in EXPECTED_SCHEMAS:
        result.add_warning(f"No schema definition found for {filename}")
        return result

    expected_headers = EXPECTED_SCHEMAS[filename]

    try:
        with file_path.open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            headers = next(reader, None)

            if not headers:
                result.add_error(f"{filename}: File is empty or has no headers")
                return result

            # Check schema compliance
            if headers != expected_headers:
                result.add_error(
                    f"{filename}: Schema mismatch\n"
                    f"  Expected: {expected_headers}\n"
                    f"  Actual:   {headers}"
                )

            # Track data for validation
            seen_ids: set[str] = set()
            id_field = ID_FIELDS.get(filename)
            required_fields = REQUIRED_FIELDS.get(filename, set())
            enum_fields = ENUM_FIELDS.get(filename, {})
            date_fields = DATE_FIELDS.get(filename, set())
            time_fields = TIME_FIELDS.get(filename, set())
            numeric_fields = NUMERIC_FIELDS.get(filename, {})
            time_range_fields = TIME_RANGE_FIELDS.get(filename, {})
            duration_fields = DURATION_CONSISTENCY_FIELDS.get(filename, {})
            date_range_fields = DATE_RANGE_FIELDS.get(filename, {})

            # Validate data rows
            for row_num, row in enumerate(reader, start=2):
                if len(row) != len(headers):
                    result.add_error(f"{filename}: Row {row_num} has {len(row)} columns, expected {len(headers)}")
                    continue

                row_data = dict(zip(headers, row, strict=False))

                # Check for duplicate IDs
                if id_field and id_field in row_data:
                    id_value = row_data[id_field]
                    if id_value in seen_ids:
                        result.add_error(f"{filename}: Duplicate ID '{id_value}' found at row {row_num}")
                    seen_ids.add(id_value)

                # Check required fields
                for field in required_fields:
                    if field in row_data and not row_data[field].strip():
                        result.add_error(f"{filename}: Required field '{field}' is empty at row {row_num}")

                # Check enum values
                for field, allowed_values in enum_fields.items():
                    if field in row_data and row_data[field].strip() and row_data[field] not in allowed_values:
                        result.add_error(
                            f"{filename}: Invalid value '{row_data[field]}' for field '{field}' at row {row_num}. "
                            f"Allowed values: {allowed_values}"
                        )

                # Check date formats
                for field in date_fields:
                    if field in row_data and row_data[field].strip() and not validate_date_format(row_data[field]):
                        result.add_error(f"{filename}: Invalid date format '{row_data[field]}' for field '{field}' at row {row_num}")

                # Check time formats
                for field in time_fields:
                    if field in row_data and row_data[field].strip() and not validate_time_format(row_data[field]):
                        result.add_error(f"{filename}: Invalid time format '{row_data[field]}' for field '{field}' at row {row_num}")

                # Check numeric fields
                for field, constraints in numeric_fields.items():
                    if field in row_data and row_data[field].strip():
                        min_val_raw = constraints.get("min")
                        max_val_raw = constraints.get("max")
                        min_val = None if min_val_raw is None else cast(int | float, min_val_raw)
                        max_val = None if max_val_raw is None else cast(int | float, max_val_raw)
                        is_valid, error_msg = validate_numeric_field(
                            row_data[field],
                            field,
                            min_val=min_val,
                            max_val=max_val,
                            is_integer=constraints.get("type") == "int"
                        )
                        if not is_valid:
                            result.add_error(f"{filename}: {error_msg} at row {row_num}")

                # Check time ranges (start < end)
                if time_range_fields:
                    start_field = time_range_fields.get("start")
                    end_field = time_range_fields.get("end")
                    if start_field and end_field and start_field in row_data and end_field in row_data:
                        is_valid, error_msg = validate_time_range(row_data[start_field], row_data[end_field])
                        if not is_valid:
                            result.add_error(f"{filename}: {error_msg} at row {row_num}")

                # Check duration consistency
                if duration_fields:
                    start_field = duration_fields.get("start_time")
                    end_field = duration_fields.get("end_time")
                    duration_field = duration_fields.get("duration")
                    if all(f is not None and f in row_data for f in [start_field, end_field, duration_field]):
                        # Type checking: at this point we know all fields are not None
                        assert start_field is not None
                        assert end_field is not None
                        assert duration_field is not None
                        is_valid, error_msg = validate_duration_consistency(
                            row_data[start_field], row_data[end_field], row_data[duration_field]
                        )
                        if not is_valid:
                            result.add_error(f"{filename}: {error_msg} at row {row_num}")

                # Check date ranges (start <= end)
                if date_range_fields:
                    start_field = date_range_fields.get("start")
                    end_field = date_range_fields.get("end")
                    if start_field and end_field and start_field in row_data and end_field in row_data:
                        is_valid, error_msg = validate_date_range(
                            row_data[start_field], row_data[end_field], (start_field, end_field)
                        )
                        if not is_valid:
                            result.add_error(f"{filename}: {error_msg} at row {row_num}")

    except UnicodeDecodeError as e:
        result.add_error(f"{filename}: Encoding error - {e}")
    except Exception as e:
        result.add_error(f"{filename}: Unexpected error - {e}")

    return result


def validate_foreign_keys(canonical_dir: Path) -> list[str]:
    """Validate foreign key references between CSV files."""
    errors = []

    # Load all IDs for reference checking
    project_ids = set()
    task_ids = set()
    habit_ids = set()

    # Load project IDs
    projects_file = canonical_dir / "projects.csv"
    if projects_file.exists():
        try:
            with projects_file.open(newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                project_ids = {row.get("project_id", "") for row in reader if row.get("project_id", "").strip()}
        except Exception as e:
            errors.append(f"Failed to load project IDs: {e}")

    # Load task IDs
    tasks_file = canonical_dir / "tasks.csv"
    if tasks_file.exists():
        try:
            with tasks_file.open(newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                task_ids = {row.get("task_id", "") for row in reader if row.get("task_id", "").strip()}
        except Exception as e:
            errors.append(f"Failed to load task IDs: {e}")

    # Load habit IDs
    habits_file = canonical_dir / "habits.csv"
    if habits_file.exists():
        try:
            with habits_file.open(newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                habit_ids = {row.get("habit_id", "") for row in reader if row.get("habit_id", "").strip()}
        except Exception as e:
            errors.append(f"Failed to load habit IDs: {e}")

    # Check foreign keys in tasks.csv
    if tasks_file.exists():
        try:
            with tasks_file.open(newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row_num, row in enumerate(reader, start=2):
                    project_id = row.get("project_id", "").strip()
                    if project_id and project_id not in project_ids:
                        errors.append(f"tasks.csv row {row_num}: Invalid project_id '{project_id}'")
        except Exception as e:
            errors.append(f"Failed to validate task foreign keys: {e}")

    # Check foreign keys in time_blocks.csv
    time_blocks_file = canonical_dir / "time_blocks.csv"
    if time_blocks_file.exists():
        try:
            with time_blocks_file.open(newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row_num, row in enumerate(reader, start=2):
                    task_id = row.get("task_id", "").strip()
                    if task_id and task_id not in task_ids:
                        errors.append(f"time_blocks.csv row {row_num}: Invalid task_id '{task_id}'")
        except Exception as e:
            errors.append(f"Failed to validate time_blocks foreign keys: {e}")

    # Check foreign keys in daily_log.csv (in logs directory)
    daily_log_file = LOGS_DIR / "daily_log.csv"
    if daily_log_file.exists():
        try:
            with daily_log_file.open(newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row_num, row in enumerate(reader, start=2):
                    habit_id = row.get("habit_id", "").strip()
                    if habit_id and habit_id not in habit_ids:
                        errors.append(f"daily_log.csv row {row_num}: Invalid habit_id '{habit_id}'")
        except Exception as e:
            errors.append(f"Failed to validate daily_log foreign keys: {e}")

    return errors


def main() -> None:
    """Run comprehensive CSV validation."""
    print("🔍 CSV Data Integrity Validation")
    print("=" * 60)

    all_files = []

    # Canonical data files
    for filename in EXPECTED_SCHEMAS:
        if filename in ["daily_log.csv", "activity_log.csv"]:
            all_files.append(LOGS_DIR / filename)
        else:
            all_files.append(CANONICAL_DIR / filename)

    total_errors = 0
    total_warnings = 0

    # Validate each file
    for file_path in all_files:
        result = validate_csv_schema(file_path)

        status_icon = "✅" if result.passed else "❌"
        print(f"\n{status_icon} {file_path.relative_to(REPO_ROOT)}")

        if result.errors:
            for error in result.errors:
                print(f"   🔴 ERROR: {error}")
                total_errors += 1

        if result.warnings:
            for warning in result.warnings:
                print(f"   🟡 WARNING: {warning}")
                total_warnings += 1

        if result.passed and not result.warnings:
            print("   ✅ Schema and data validation passed")

    # Validate foreign key references
    print("\n🔗 Foreign Key Validation")
    foreign_key_errors = validate_foreign_keys(CANONICAL_DIR)

    if foreign_key_errors:
        for error in foreign_key_errors:
            print(f"   🔴 ERROR: {error}")
            total_errors += len(foreign_key_errors)
    else:
        print("   ✅ All foreign key references are valid")

    # Summary
    print("\n" + "=" * 60)
    print("📊 Validation Summary:")
    print(f"   • Total errors: {total_errors}")
    print(f"   • Total warnings: {total_warnings}")

    if total_errors == 0:
        print("   🎉 All validation checks passed!")
    else:
        print("   ⚠️  Issues found that need attention")
        exit(1)


if __name__ == "__main__":
    main()
