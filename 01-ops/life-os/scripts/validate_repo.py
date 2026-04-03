#!/usr/bin/env python3
"""Repo-local validation and lint checks for the life-os scaffold."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
COMMAND_RE = re.compile(r"`(/[\w-]+)`")
DATE_COLUMNS = (
    "date",
    "target_date",
    "due_date",
    "start_date",
    "scheduled_date",
    "last_updated",
)
TIME_COLUMNS = (
    "start",
    "end",
    "start_time",
    "end_time",
    "scheduled_start",
    "scheduled_end",
)


def markdown_docs() -> list[Path]:
    """Return tracked markdown docs that should participate in validation."""
    docs_dir = REPO_ROOT / "docs"
    return [
        REPO_ROOT / "README.md",
        REPO_ROOT / "CLAUDE.md",
        *sorted(docs_dir.glob("*.md")),
    ]


def command_reference_docs() -> list[Path]:
    """Return docs that are expected to mention real, built-in commands."""
    return [
        REPO_ROOT / "README.md",
        REPO_ROOT / "CLAUDE.md",
        REPO_ROOT / "docs" / "getting-started.md",
        REPO_ROOT / "docs" / "google-calendar.md",
        REPO_ROOT / "docs" / "skills-reference.md",
    ]


def csv_files() -> list[Path]:
    """Return tracked canonical and log CSV files at the current repo root."""
    data_dir = REPO_ROOT / "01-ops" / "life-os" / "data" / "canonical"
    log_dir = REPO_ROOT / "01-ops" / "life-os" / "logs"
    return sorted(data_dir.glob("*.csv")) + sorted(log_dir.glob("*.csv"))


def fail(message: str) -> None:
    print(f"ERROR: {message}")


def validate_required_paths() -> list[str]:
    """Validate that all required scaffold files and directories exist.

    Returns:
        List of validation error messages for missing required paths.

    Checks for essential scaffold components:
        - .claude/commands directory
        - Example configuration files
        - Core Python scripts
    """
    paths = [
        REPO_ROOT / ".claude" / "commands",
        REPO_ROOT / "01-ops" / "life-os" / "config" / "profile.example.json",
        REPO_ROOT / "01-ops" / "life-os" / "config" / "calendar_feeds.example.json",
        REPO_ROOT / "01-ops" / "life-os" / "scripts" / "gcal.py",
    ]
    errors = []
    for path in paths:
        if not path.exists():
            errors.append(f"Missing required path: {path.relative_to(REPO_ROOT)}")
    return errors


def validate_csv_headers() -> list[str]:
    """Validate CSV header row structure and content.

    Returns:
        List of validation error messages for problematic CSV headers.

    Validates:
        - Headers exist and are readable
        - No empty header cells
        - No duplicate column names
        - No problematic characters that could break parsing
        - File encoding is valid UTF-8
    """
    errors = []
    for csv_path in csv_files():
        try:
            with csv_path.open(newline="", encoding="utf-8") as handle:
                reader = csv.reader(handle)
                header = next(reader, None)
        except (FileNotFoundError, PermissionError, UnicodeDecodeError) as e:
            errors.append(f"Cannot read CSV file {csv_path.relative_to(REPO_ROOT)}: {e}")
            continue

        if not header:
            errors.append(f"CSV missing header row: {csv_path.relative_to(REPO_ROOT)}")
            continue

        # Check for blank header cells
        if any(not cell.strip() for cell in header):
            errors.append(f"CSV has blank header cells: {csv_path.relative_to(REPO_ROOT)}")

        # Check for duplicate header cells
        if len(set(header)) != len(header):
            errors.append(f"CSV has duplicate header cells: {csv_path.relative_to(REPO_ROOT)}")

        # Check for suspicious characters in headers
        for cell in header:
            if any(char in cell for char in ['"', "'", '\n', '\r', '\t']):
                errors.append(f"CSV header contains suspicious characters: {csv_path.relative_to(REPO_ROOT)}")
                break

    return errors


def validate_csv_structure() -> list[str]:
    """Validate CSV file structure for consistency with performance optimizations.

    Returns:
        List of validation error messages for structural issues.

    Performance features:
        - Early termination after first structure error per file
        - File size limits to prevent processing extremely large files
        - Efficient line-by-line reading without loading entire file
    """
    errors = []
    max_file_size_mb = 10  # Skip files larger than 10MB
    max_lines_to_check = 1000  # Limit validation to first 1000 lines for performance

    for csv_path in csv_files():
        try:
            # Check file size before processing
            file_size = csv_path.stat().st_size
            if file_size > max_file_size_mb * 1024 * 1024:
                errors.append(
                    f"CSV file {csv_path.relative_to(REPO_ROOT)} is too large ({file_size // 1024 // 1024}MB) "
                    f"for structure validation (max: {max_file_size_mb}MB)"
                )
                continue

            with csv_path.open(newline="", encoding="utf-8") as handle:
                reader = csv.reader(handle)
                header = next(reader, None)
                if not header:
                    continue

                header_count = len(header)
                line_num = 2  # Start after header
                lines_checked = 0

                for row in reader:
                    if len(row) != header_count:
                        errors.append(
                            f"CSV row mismatch at line {line_num} in {csv_path.relative_to(REPO_ROOT)}: "
                            f"expected {header_count} columns, got {len(row)}"
                        )
                        break  # Stop after first mismatch to avoid noise

                    line_num += 1
                    lines_checked += 1

                    # Limit validation for very large files
                    if lines_checked >= max_lines_to_check:
                        # Don't count remaining lines to avoid expensive file operation
                        errors.append(
                            f"CSV file {csv_path.relative_to(REPO_ROOT)} has more than {max_lines_to_check} rows, "
                            f"only validated first {max_lines_to_check} data rows"
                        )
                        break

        except (FileNotFoundError, PermissionError, UnicodeDecodeError):
            # Already handled in validate_csv_headers
            pass

    return errors


def _validate_numeric_field(value: str, field_name: str, line_num: int, csv_path_str: str,
                           min_val: float | None = None, max_val: float | None = None,
                           allow_decimal: bool = True) -> list[str]:
    """Validate numeric field with optional range checking.

    Args:
        value: The string value to validate as numeric
        field_name: Name of the field for error messages
        line_num: Line number in CSV for error messages
        csv_path_str: CSV file path for error messages
        min_val: Optional minimum allowed value
        max_val: Optional maximum allowed value
        allow_decimal: Whether to allow decimal values (default: True)

    Returns:
        List of validation error messages
    """
    errors: list[str] = []
    if not value.strip():
        return errors  # Empty values handled elsewhere

    try:
        if allow_decimal:
            num_val = float(value)
        else:
            if '.' in value:
                errors.append(f"Field '{field_name}' at line {line_num} in {csv_path_str} should be an integer, got '{value}'")
                return errors
            num_val = int(value)

        if min_val is not None and num_val < min_val:
            errors.append(f"Field '{field_name}' at line {line_num} in {csv_path_str} is below minimum {min_val}, got {num_val}")

        if max_val is not None and num_val > max_val:
            errors.append(f"Field '{field_name}' at line {line_num} in {csv_path_str} exceeds maximum {max_val}, got {num_val}")

    except ValueError:
        errors.append(f"Invalid numeric value '{value}' for '{field_name}' at line {line_num} in {csv_path_str}")

    return errors


def _validate_boolean_field(value: str, field_name: str, line_num: int, csv_path_str: str) -> list[str]:
    """Validate boolean field accepts standard boolean representations.

    Args:
        value: The string value to validate as boolean
        field_name: Name of the field for error messages
        line_num: Line number in CSV for error messages
        csv_path_str: CSV file path for error messages

    Returns:
        List of validation error messages

    Accepts: true, false, 1, 0, yes, no (case insensitive)
    """
    if not value.strip():
        return []  # Empty values handled elsewhere

    if value.lower() not in ["true", "false", "1", "0", "yes", "no"]:
        return [f"Invalid boolean value '{value}' for '{field_name}' at line {line_num} in {csv_path_str}. Use true/false"]

    return []


def _validate_id_field(value: str, field_name: str, line_num: int, csv_path_str: str) -> list[str]:
    """Validate ID field format for data integrity and safety.

    Args:
        value: The string value to validate as an ID
        field_name: Name of the field for error messages
        line_num: Line number in CSV for error messages
        csv_path_str: CSV file path for error messages

    Returns:
        List of validation error messages

    Validates:
        - No whitespace (spaces, tabs, newlines)
        - Reasonable length (max 100 characters)
        - No problematic characters that could break CSV parsing
        - Not empty after trimming
    """
    errors: list[str] = []
    if not value.strip():
        return errors  # Empty values handled elsewhere

    # Check for spaces
    if ' ' in value:
        errors.append(f"ID field '{field_name}' at line {line_num} in {csv_path_str} contains spaces: '{value}'")

    # Check length (reasonable limits)
    if len(value) > 100:
        errors.append(f"ID field '{field_name}' at line {line_num} in {csv_path_str} is too long (max 100 chars): '{value[:50]}...'")

    if len(value.strip()) < 1:
        errors.append(f"ID field '{field_name}' at line {line_num} in {csv_path_str} is empty")

    # Check for problematic characters (basic validation)
    problematic_chars = ['"', "'", '\n', '\r', '\t', ',', ';']
    for char in problematic_chars:
        if char in value:
            errors.append(f"ID field '{field_name}' at line {line_num} in {csv_path_str} contains problematic character '{char}': '{value}'")

    return errors


def validate_csv_schemas() -> list[str]:
    """Validate CSV files against expected schemas and data quality."""
    errors = []

    # Define expected schemas for each canonical file
    schemas = {
        "habits.csv": {
            "required_columns": ["habit_id", "area", "name", "frequency", "target_per_week", "min_value", "unit", "active"],
            "optional_columns": ["notes", "last_updated"],
            "enums": {
                "frequency": ["daily", "weekly"],
                "active": ["true", "false"]
            },
            "numeric_fields": {
                "target_per_week": {"min_val": 0, "max_val": 7, "allow_decimal": False},
                "min_value": {"min_val": 0, "max_val": 1440, "allow_decimal": True}
            },
            "id_fields": ["habit_id"],
            "boolean_fields": ["active"]
        },
        "goals.csv": {
            "required_columns": ["goal_id", "area", "title"],
            "optional_columns": ["horizon", "target_date", "metric_name", "metric_target", "metric_current", "status", "last_updated", "notes"],
            "enums": {
                "horizon": ["quarter", "year", "month"],
                "status": ["active", "completed", "paused", "dropped"]
            },
            "numeric_fields": {
                "metric_target": {"min_val": 0, "allow_decimal": True},
                "metric_current": {"min_val": 0, "allow_decimal": True}
            },
            "id_fields": ["goal_id"]
        },
        "tasks.csv": {
            "required_columns": ["task_id", "title", "domain"],
            "optional_columns": ["project_id", "status", "priority", "effort_mins", "due_date", "energy", "context", "source", "next_step", "scheduled_date", "scheduled_start", "scheduled_end", "last_updated", "notes"],
            "enums": {
                "status": ["queued", "in_progress", "blocked", "completed"],
                "energy": ["low", "medium", "high"],
                "source": ["manual", "auto", "imported"]
            },
            "numeric_fields": {
                "priority": {"min_val": 1, "max_val": 5, "allow_decimal": False},
                "effort_mins": {"min_val": 1, "max_val": 960, "allow_decimal": False}
            },
            "id_fields": ["task_id", "project_id"]
        },
        "projects.csv": {
            "required_columns": ["project_id", "area", "name"],
            "optional_columns": ["status", "start_date", "target_date", "description", "last_updated", "notes", "active"],
            "enums": {
                "status": ["planning", "active", "paused", "completed"],
                "active": ["true", "false"]
            },
            "id_fields": ["project_id"],
            "boolean_fields": ["active"]
        },
        "time_blocks.csv": {
            "required_columns": ["block_id", "date", "start", "end", "title"],
            "optional_columns": ["domain", "task_id", "source", "status", "notes"],
            "enums": {
                "source": ["manual", "auto_planner", "imported"],
                "status": ["planned", "in_progress", "completed", "skipped"]
            },
            "id_fields": ["block_id", "task_id"]
        },
        "time_logs.csv": {
            "required_columns": ["log_id", "date", "start_time", "end_time", "activity"],
            "optional_columns": ["domain", "duration_mins", "task_id", "notes", "last_updated"],
            "numeric_fields": {
                "duration_mins": {"min_val": 1, "max_val": 1440, "allow_decimal": False}
            },
            "id_fields": ["log_id", "task_id"]
        },
        "calendar_events.csv": {
            "required_columns": ["event_id", "date", "start_time", "end_time", "title"],
            "optional_columns": ["location", "attendees", "source", "calendar", "notes"],
            "enums": {
                "source": ["google_calendar", "manual", "outlook"]
            },
            "id_fields": ["event_id"]
        }
    }

    for csv_path in csv_files():
        filename = csv_path.name
        if filename not in schemas:
            continue

        schema = schemas[filename]

        try:
            with csv_path.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                header = reader.fieldnames

                if not header:
                    errors.append(f"CSV has no header: {csv_path.relative_to(REPO_ROOT)}")
                    continue

                # Check required columns
                for required_col in schema["required_columns"]:
                    if required_col not in header:
                        errors.append(f"Missing required column '{required_col}' in {csv_path.relative_to(REPO_ROOT)}")

                allowed_columns = set(schema["required_columns"]) | set(
                    schema.get("optional_columns", [])
                )
                unexpected_columns = [
                    column for column in header if column not in allowed_columns
                ]
                if unexpected_columns:
                    errors.append(
                        f"Unexpected column(s) {unexpected_columns} in {csv_path.relative_to(REPO_ROOT)}"
                    )

                # Validate data rows with enhanced type checking
                line_num = 2  # Start after header
                csv_path_str = str(csv_path.relative_to(REPO_ROOT))

                for row in reader:
                    # Check required fields are not empty
                    for required_col in schema["required_columns"]:
                        if required_col in row and not row[required_col].strip():
                            errors.append(f"Empty required field '{required_col}' at line {line_num} in {csv_path_str}")

                    # Validate enums
                    if "enums" in schema:
                        enums_dict = schema["enums"]
                        assert isinstance(enums_dict, dict)
                        for col, valid_values in enums_dict.items():
                            if col in row and row[col].strip() and row[col] not in valid_values:
                                errors.append(f"Invalid value '{row[col]}' for '{col}' at line {line_num} in {csv_path_str}. Valid: {valid_values}")

                    # Validate numeric fields with range checking
                    if "numeric_fields" in schema:
                        numeric_fields_dict = schema["numeric_fields"]
                        assert isinstance(numeric_fields_dict, dict)
                        for col, constraints in numeric_fields_dict.items():
                            if col in row and row[col].strip():
                                errors.extend(_validate_numeric_field(
                                    row[col], col, line_num, csv_path_str,
                                    constraints.get("min_val"),
                                    constraints.get("max_val"),
                                    constraints.get("allow_decimal", True)
                                ))

                    # Validate boolean fields
                    if "boolean_fields" in schema:
                        for col in schema["boolean_fields"]:
                            if col in row and row[col].strip():
                                errors.extend(_validate_boolean_field(row[col], col, line_num, csv_path_str))

                    # Validate ID fields
                    if "id_fields" in schema:
                        for col in schema["id_fields"]:
                            if col in row and row[col].strip():
                                errors.extend(_validate_id_field(row[col], col, line_num, csv_path_str))

                    # Validate date formats with better error messages
                    for col in DATE_COLUMNS:
                        if col in row and row[col].strip():
                            try:
                                parsed_date = datetime.strptime(row[col], "%Y-%m-%d")
                                # Additional validation for reasonable date ranges
                                if parsed_date.year < 1900 or parsed_date.year > 2100:
                                    errors.append(f"Date '{row[col]}' in '{col}' at line {line_num} in {csv_path_str} has unreasonable year")
                            except ValueError:
                                errors.append(f"Invalid date format '{row[col]}' in '{col}' at line {line_num} in {csv_path_str}. Use YYYY-MM-DD")

                    # Validate time formats with better error messages
                    for col in TIME_COLUMNS:
                        if col in row and row[col].strip():
                            time_val = row[col].strip()
                            try:
                                parsed_time = datetime.strptime(time_val, "%H:%M")
                                # Additional validation for reasonable time values
                                hour = parsed_time.hour
                                minute = parsed_time.minute
                                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                                    errors.append(f"Time '{time_val}' in '{col}' at line {line_num} in {csv_path_str} has invalid hour/minute values")
                            except ValueError:
                                # Try to provide more specific error messages
                                if ':' not in time_val:
                                    errors.append(f"Time format '{time_val}' in '{col}' at line {line_num} in {csv_path_str} missing colon. Use HH:MM")
                                elif time_val.count(':') > 1:
                                    errors.append(f"Time format '{time_val}' in '{col}' at line {line_num} in {csv_path_str} has too many colons. Use HH:MM")
                                else:
                                    errors.append(f"Invalid time format '{time_val}' in '{col}' at line {line_num} in {csv_path_str}. Use HH:MM")

                    # Cross-field validation for time ranges
                    if filename == "time_blocks.csv" and "start" in row and "end" in row:
                        start_str = row["start"].strip()
                        end_str = row["end"].strip()
                        if start_str and end_str:
                            try:
                                start_time = datetime.strptime(start_str, "%H:%M").time()
                                end_time = datetime.strptime(end_str, "%H:%M").time()
                                if start_time >= end_time:
                                    # Allow overnight blocks but warn about same time
                                    if start_time == end_time:
                                        errors.append(f"Start and end times are identical at line {line_num} in {csv_path_str}: {start_str}")
                            except ValueError:
                                pass  # Individual time validation will catch these

                    line_num += 1

        except (FileNotFoundError, PermissionError, UnicodeDecodeError) as e:
            errors.append(f"Cannot read CSV file {csv_path.relative_to(REPO_ROOT)}: {e}")

    return errors


def validate_markdown_links() -> list[str]:
    errors = []
    for doc_path in markdown_docs():
        try:
            content = doc_path.read_text(encoding="utf-8")
        except (FileNotFoundError, PermissionError, UnicodeDecodeError) as e:
            errors.append(f"Cannot read markdown file {doc_path.relative_to(REPO_ROOT)}: {e}")
            continue
        for target in LINK_RE.findall(content):
            if (
                target.startswith("http://")
                or target.startswith("https://")
                or target.startswith("#")
                or target.startswith("mailto:")
            ):
                continue
            resolved = (doc_path.parent / target).resolve()
            if not resolved.exists():
                errors.append(
                    f"Broken relative link in {doc_path.relative_to(REPO_ROOT)}: {target}"
                )
    return errors


def validate_command_references() -> list[str]:
    command_dir = REPO_ROOT / ".claude" / "commands"
    defined = {f"/{path.stem}" for path in command_dir.glob("*.md")}
    errors = []
    for doc_path in command_reference_docs():
        content = doc_path.read_text(encoding="utf-8")
        for command in COMMAND_RE.findall(content):
            if command not in defined:
                errors.append(
                    f"Unknown command reference in {doc_path.relative_to(REPO_ROOT)}: {command}"
                )
    return errors


def validate_command_coverage() -> list[str]:
    """Catch unreferenced command files before they turn into dead scaffold code."""
    command_dir = REPO_ROOT / ".claude" / "commands"
    referenced = set()

    for doc_path in markdown_docs():
        content = doc_path.read_text(encoding="utf-8")
        referenced.update(COMMAND_RE.findall(content))

    errors = []
    for command_path in sorted(command_dir.glob("*.md")):
        command = f"/{command_path.stem}"
        if command not in referenced:
            errors.append(
                f"Command file is not referenced in docs: {command_path.relative_to(REPO_ROOT)}"
            )
    return errors


def lint_whitespace() -> list[str]:
    errors = []
    paths = markdown_docs() + sorted((REPO_ROOT / ".claude" / "commands").glob("*.md"))
    for path in paths:
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.endswith(" ") or line.endswith("\t"):
                errors.append(f"Trailing whitespace in {path.relative_to(REPO_ROOT)}:{line_no}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lint", action="store_true", help="Run lint-style checks too.")
    args = parser.parse_args()

    errors = []
    errors.extend(validate_required_paths())
    errors.extend(validate_csv_headers())
    errors.extend(validate_csv_structure())
    errors.extend(validate_csv_schemas())
    errors.extend(validate_markdown_links())
    errors.extend(validate_command_references())
    errors.extend(validate_command_coverage())
    if args.lint:
        errors.extend(lint_whitespace())

    if errors:
        for error in errors:
            fail(error)
        return 1

    mode = "lint" if args.lint else "validation"
    print(f"{mode.capitalize()} checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
