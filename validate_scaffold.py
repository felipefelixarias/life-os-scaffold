#!/usr/bin/env python3
"""Comprehensive scaffold validation for CSV data integrity and command path validation."""

from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path
from typing import Any

# Repository root path
REPO_ROOT = Path(__file__).resolve().parent

# Schema definitions based on docs/csv-schemas.md
CSV_SCHEMAS = {
    "habits.csv": {
        "expected_headers": [
            "habit_id",
            "area",
            "name",
            "frequency",
            "target_per_week",
            "min_value",
            "unit",
            "active",
            "notes",
            "last_updated",
        ],
        "required_fields": [
            "habit_id",
            "area",
            "name",
            "frequency",
            "target_per_week",
            "min_value",
            "unit",
            "active",
        ],
        "id_field": "habit_id",
        "date_fields": ["last_updated"],
        "enum_fields": {"frequency": ["daily", "weekly"], "active": ["true", "false"]},
    },
    "goals.csv": {
        "expected_headers": [
            "goal_id",
            "area",
            "title",
            "horizon",
            "target_date",
            "metric_name",
            "metric_target",
            "metric_current",
            "status",
            "last_updated",
            "notes",
        ],
        "required_fields": ["goal_id", "area", "title"],
        "id_field": "goal_id",
        "date_fields": ["target_date", "last_updated"],
        "enum_fields": {
            "horizon": ["quarter", "year", "month"],
            "status": ["active", "completed", "paused", "dropped"],
        },
    },
    "tasks.csv": {
        "expected_headers": [
            "task_id",
            "project_id",
            "title",
            "domain",
            "status",
            "priority",
            "effort_mins",
            "due_date",
            "energy",
            "context",
            "source",
            "next_step",
            "scheduled_date",
            "scheduled_start",
            "scheduled_end",
            "last_updated",
            "notes",
        ],
        "required_fields": ["task_id", "title", "domain"],
        "id_field": "task_id",
        "date_fields": ["due_date", "scheduled_date", "last_updated"],
        "enum_fields": {
            "status": ["queued", "in_progress", "blocked", "completed"],
            "energy": ["low", "medium", "high"],
            "source": ["manual", "auto", "imported"],
        },
    },
    "projects.csv": {
        "expected_headers": [
            "project_id",
            "area",
            "name",
            "status",
            "start_date",
            "target_date",
            "description",
            "last_updated",
            "notes",
            "active",
        ],
        "required_fields": ["project_id", "area", "name"],
        "id_field": "project_id",
        "date_fields": ["start_date", "target_date", "last_updated"],
        "enum_fields": {
            "status": ["planning", "active", "paused", "completed"],
            "active": ["true", "false"],
        },
    },
    "time_blocks.csv": {
        "expected_headers": [
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
        "required_fields": ["block_id", "date", "start", "end", "title"],
        "id_field": "block_id",
        "date_fields": ["date"],
        "time_fields": ["start", "end"],
        "enum_fields": {
            "source": ["manual", "auto_planner", "imported"],
            "status": ["planned", "in_progress", "completed", "skipped"],
        },
    },
    "time_logs.csv": {
        "expected_headers": [
            "log_id",
            "date",
            "activity",
            "domain",
            "duration_mins",
            "start_time",
            "end_time",
            "notes",
            "last_updated",
        ],
        "required_fields": ["log_id", "date", "activity", "start_time", "end_time"],
        "id_field": "log_id",
        "date_fields": ["date", "last_updated"],
        "time_fields": ["start_time", "end_time"],
    },
    "calendar_events.csv": {
        "expected_headers": [
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
        "required_fields": ["event_id", "date", "start_time", "end_time", "title"],
        "id_field": "event_id",
        "date_fields": ["date"],
        "time_fields": ["start_time", "end_time"],
        "enum_fields": {"source": ["google_calendar", "manual", "outlook"]},
    },
}

# Log file schemas (simpler structure)
LOG_SCHEMAS = {
    "daily_log.csv": {
        "expected_headers": ["date", "habit_id", "value", "notes"],
        "required_fields": ["date", "habit_id", "value"],
        "date_fields": ["date"],
    },
    "activity_log.csv": {
        "expected_headers": ["timestamp", "event", "details"],
        "required_fields": ["timestamp", "event"],
        "datetime_fields": ["timestamp"],
    },
}


def validate_date_format(date_str: str) -> bool:
    """Validate YYYY-MM-DD date format."""
    if not date_str or date_str.strip() == "":
        return True  # Empty dates are allowed in optional fields
    try:
        datetime.strptime(date_str.strip(), "%Y-%m-%d")
        return True
    except ValueError:
        return False


def validate_time_format(time_str: str) -> bool:
    """Validate HH:MM time format."""
    if not time_str or time_str.strip() == "":
        return True  # Empty times are allowed in optional fields
    try:
        datetime.strptime(time_str.strip(), "%H:%M")
        return True
    except ValueError:
        return False


def validate_datetime_format(datetime_str: str) -> bool:
    """Validate ISO datetime format."""
    if not datetime_str or datetime_str.strip() == "":
        return True
    try:
        datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def validate_csv_file(csv_path: Path, schema: dict[str, Any]) -> list[str]:
    """Validate a single CSV file against its schema."""
    errors = []

    if not csv_path.exists():
        return [f"File not found: {csv_path.relative_to(REPO_ROOT)}"]

    try:
        with csv_path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            # Check headers
            if reader.fieldnames != schema["expected_headers"]:
                errors.append(f"Header mismatch in {csv_path.name}")
                errors.append(f"  Expected: {schema['expected_headers']}")
                errors.append(
                    f"  Actual:   {list(reader.fieldnames) if reader.fieldnames else []}"
                )
                return errors  # Can't continue validation with wrong headers

            # Track IDs for duplicate detection
            seen_ids: set[str] = set()
            row_num = 1

            for row in reader:
                row_num += 1

                # Check required fields
                for required_field in schema["required_fields"]:
                    if not row.get(required_field, "").strip():
                        errors.append(
                            f"{csv_path.name}:{row_num} - Required field '{required_field}' is empty"
                        )

                # Check ID uniqueness
                if "id_field" in schema:
                    id_value = row.get(schema["id_field"], "").strip()
                    if id_value:
                        if id_value in seen_ids:
                            errors.append(
                                f"{csv_path.name}:{row_num} - Duplicate ID '{id_value}'"
                            )
                        seen_ids.add(id_value)

                # Check date fields
                for date_field in schema.get("date_fields", []):
                    date_value = row.get(date_field, "")
                    if not validate_date_format(date_value):
                        errors.append(
                            f"{csv_path.name}:{row_num} - Invalid date format in '{date_field}': '{date_value}'"
                        )

                # Check time fields
                for time_field in schema.get("time_fields", []):
                    time_value = row.get(time_field, "")
                    if not validate_time_format(time_value):
                        errors.append(
                            f"{csv_path.name}:{row_num} - Invalid time format in '{time_field}': '{time_value}'"
                        )

                # Check datetime fields
                for datetime_field in schema.get("datetime_fields", []):
                    datetime_value = row.get(datetime_field, "")
                    if not validate_datetime_format(datetime_value):
                        errors.append(
                            f"{csv_path.name}:{row_num} - Invalid datetime format in '{datetime_field}': '{datetime_value}'"
                        )

                # Check enum fields
                for enum_field, valid_values in schema.get("enum_fields", {}).items():
                    field_value = row.get(enum_field, "").strip()
                    if field_value and field_value not in valid_values:
                        errors.append(
                            f"{csv_path.name}:{row_num} - Invalid value in '{enum_field}': '{field_value}' (valid: {valid_values})"
                        )

    except Exception as e:
        errors.append(f"Error reading {csv_path.name}: {e}")

    return errors


def validate_all_csv_files() -> list[str]:
    """Validate all CSV files in canonical data and logs directories."""
    all_errors = []

    # Validate canonical CSV files
    canonical_dir = REPO_ROOT / "01-ops" / "life-os" / "data" / "canonical"
    for filename, schema in CSV_SCHEMAS.items():
        csv_path = canonical_dir / filename
        errors = validate_csv_file(csv_path, schema)
        all_errors.extend(errors)

    # Validate log CSV files
    logs_dir = REPO_ROOT / "01-ops" / "life-os" / "logs"
    for filename, schema in LOG_SCHEMAS.items():
        csv_path = logs_dir / filename
        errors = validate_csv_file(csv_path, schema)
        all_errors.extend(errors)

    return all_errors


def validate_command_file_paths() -> list[str]:
    """Validate that .claude/commands/*.md files reference correct file paths."""
    errors = []
    commands_dir = REPO_ROOT / ".claude" / "commands"

    if not commands_dir.exists():
        return ["Commands directory not found: .claude/commands/"]

    for cmd_file in commands_dir.glob("*.md"):
        try:
            content = cmd_file.read_text(encoding="utf-8")

            # Look for file path references (basic patterns)
            file_patterns = [
                r"01-ops/[^\s\)]+\.csv",
                r"01-ops/[^\s\)]+\.json",
                r"scripts/[^\s\)]+\.py",
                r"docs/[^\s\)]+\.md",
            ]

            for pattern in file_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    # Skip glob patterns and conditional references
                    if "*" in match or match.endswith("/*.csv"):
                        continue

                    # Skip references that are clearly conditional
                    match_context = content[
                        content.find(match) - 50 : content.find(match) + len(match) + 50
                    ]
                    if (
                        "if" in match_context.lower()
                        and "exists" in match_context.lower()
                    ):
                        continue

                    referenced_path = REPO_ROOT / match
                    if not referenced_path.exists():
                        errors.append(
                            f"{cmd_file.name} references non-existent path: {match}"
                        )

        except Exception as e:
            errors.append(f"Error reading command file {cmd_file.name}: {e}")

    return errors


def check_docs_for_broken_links() -> list[str]:
    """Check docs/ directory for broken links or outdated content."""
    errors = []
    docs_dir = REPO_ROOT / "docs"

    if not docs_dir.exists():
        return ["Docs directory not found"]

    for doc_file in docs_dir.glob("*.md"):
        try:
            content = doc_file.read_text(encoding="utf-8")

            # Look for relative file references
            file_references = re.findall(r"`([^`]+\.(csv|py|json|md))`", content)
            for file_ref, _ in file_references:
                if file_ref.startswith(("/", "~")):
                    continue  # Skip absolute paths

                # Skip example files and placeholders
                if "my-skill" in file_ref or "[date]" in file_ref or "_[" in file_ref:
                    continue

                # Skip files that are meant to be created by user (profile.json, habits.csv, etc.)
                if file_ref in ["profile.json", "habits.csv", "goals.csv"]:
                    continue

                referenced_path = REPO_ROOT / file_ref
                if not referenced_path.exists():
                    errors.append(
                        f"{doc_file.name} references non-existent file: {file_ref}"
                    )

        except Exception as e:
            errors.append(f"Error reading docs file {doc_file.name}: {e}")

    return errors


def main() -> None:
    """Run comprehensive scaffold validation."""
    print("🔍 Life-OS Scaffold Validation")
    print("=" * 50)

    all_errors = []

    # 1. Validate CSV data integrity
    print("\n📊 Validating CSV data integrity...")
    csv_errors = validate_all_csv_files()
    if csv_errors:
        print(f"❌ Found {len(csv_errors)} CSV validation errors:")
        for error in csv_errors:
            print(f"  • {error}")
        all_errors.extend(csv_errors)
    else:
        print("✅ All CSV files are valid")

    # 2. Validate command file paths
    print("\n📋 Validating command file paths...")
    cmd_errors = validate_command_file_paths()
    if cmd_errors:
        print(f"❌ Found {len(cmd_errors)} command path errors:")
        for error in cmd_errors:
            print(f"  • {error}")
        all_errors.extend(cmd_errors)
    else:
        print("✅ All command file paths are valid")

    # 3. Check docs for broken links
    print("\n📖 Checking docs for broken links...")
    doc_errors = check_docs_for_broken_links()
    if doc_errors:
        print(f"❌ Found {len(doc_errors)} documentation errors:")
        for error in doc_errors:
            print(f"  • {error}")
        all_errors.extend(doc_errors)
    else:
        print("✅ All documentation references are valid")

    # Summary
    print(f"\n{'=' * 50}")
    if all_errors:
        print(f"❌ Validation FAILED with {len(all_errors)} total errors")
        exit(1)
    else:
        print("✅ Validation PASSED - All checks successful!")


if __name__ == "__main__":
    main()
