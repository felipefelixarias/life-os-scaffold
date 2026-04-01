#!/usr/bin/env python3
"""Repo-local validation and lint checks for the life-os scaffold."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import datetime, date
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "01-ops" / "life-os" / "data" / "canonical"
LOG_DIR = REPO_ROOT / "01-ops" / "life-os" / "logs"
CSV_FILES = sorted(DATA_DIR.glob("*.csv")) + sorted(LOG_DIR.glob("*.csv"))
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
COMMAND_RE = re.compile(r"`(/[\w-]+)`")


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


def fail(message: str) -> None:
    print(f"ERROR: {message}")


def validate_config_files() -> list[str]:
    """Validate configuration files exist and have valid structure."""
    errors = []

    # Check if profile.json exists and is valid
    profile_path = REPO_ROOT / "01-ops" / "life-os" / "config" / "profile.json"
    profile_example_path = REPO_ROOT / "01-ops" / "life-os" / "config" / "profile.example.json"

    if not profile_path.exists():
        if profile_example_path.exists():
            errors.append(
                "Profile configuration missing. Run 'make setup' to copy from example."
            )
        else:
            errors.append("Both profile.json and profile.example.json are missing")
    else:
        try:
            with profile_path.open("r", encoding="utf-8") as f:
                import json
                profile_data = json.load(f)

            # Validate required profile fields
            required_fields = ["owner", "timezone", "energy_curve"]
            for field in required_fields:
                if field not in profile_data:
                    errors.append(f"Missing required field '{field}' in profile.json")

            # Validate energy_curve structure
            if "energy_curve" in profile_data:
                energy_curve = profile_data["energy_curve"]
                if not isinstance(energy_curve, list):
                    errors.append("energy_curve in profile.json should be an array/list")
                else:
                    # Check that energy curve has reasonable structure
                    for i, entry in enumerate(energy_curve):
                        if not isinstance(entry, dict):
                            errors.append(f"energy_curve entry {i} should be an object with 'time' and 'energy' fields")
                        elif "time" not in entry or "energy" not in entry:
                            errors.append(f"energy_curve entry {i} missing required 'time' or 'energy' field")
                        elif entry.get("energy") not in ["low", "medium", "high"]:
                            errors.append(f"energy_curve entry {i} has invalid energy level: {entry.get('energy')}")

        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON in profile.json: {e}")
        except (FileNotFoundError, PermissionError) as e:
            errors.append(f"Cannot read profile.json: {e}")

    return errors


def validate_required_paths() -> list[str]:
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
    errors = []
    for csv_path in CSV_FILES:
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
    """Validate CSV file structure for consistency."""
    errors = []
    for csv_path in CSV_FILES:
        try:
            with csv_path.open(newline="", encoding="utf-8") as handle:
                reader = csv.reader(handle)
                header = next(reader, None)
                if not header:
                    continue

                header_count = len(header)
                line_num = 2  # Start after header

                for row in reader:
                    if len(row) != header_count:
                        errors.append(
                            f"CSV row mismatch at line {line_num} in {csv_path.relative_to(REPO_ROOT)}: "
                            f"expected {header_count} columns, got {len(row)}"
                        )
                        break  # Stop after first mismatch to avoid noise
                    line_num += 1

        except (FileNotFoundError, PermissionError, UnicodeDecodeError):
            # Already handled in validate_csv_headers
            pass

    return errors


def validate_file_permissions() -> list[str]:
    """Validate that critical files have appropriate permissions."""
    errors = []

    # Check that CSV files are readable and writable by owner
    for csv_path in CSV_FILES:
        if csv_path.exists():
            try:
                # Check read permission
                with csv_path.open("r", encoding="utf-8") as f:
                    pass
                # Check write permission
                if not csv_path.stat().st_mode & 0o200:
                    errors.append(f"CSV file is not writable: {csv_path.relative_to(REPO_ROOT)}")
            except (PermissionError, OSError) as e:
                errors.append(f"Permission error with CSV file {csv_path.relative_to(REPO_ROOT)}: {e}")

    return errors


def validate_csv_file_sizes() -> list[str]:
    """Validate that CSV files are not suspiciously large."""
    errors = []
    MAX_CSV_SIZE_MB = 10  # 10MB limit for CSV files

    for csv_path in CSV_FILES:
        if csv_path.exists():
            try:
                size_bytes = csv_path.stat().st_size
                size_mb = size_bytes / (1024 * 1024)
                if size_mb > MAX_CSV_SIZE_MB:
                    errors.append(
                        f"CSV file is unusually large ({size_mb:.2f}MB): {csv_path.relative_to(REPO_ROOT)}. "
                        f"Consider archiving old data."
                    )
            except OSError as e:
                errors.append(f"Cannot check file size for {csv_path.relative_to(REPO_ROOT)}: {e}")

    return errors


def validate_date_formats_enhanced(date_str: str, field_name: str, line_num: int, filename: str) -> list[str]:
    """Enhanced date format validation with more comprehensive checks."""
    errors = []

    if not date_str.strip():
        return errors  # Empty dates are often allowed

    try:
        parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()

        # Check for reasonable date ranges (not too far in past/future)
        current_year = date.today().year
        if parsed_date.year < 1900 or parsed_date.year > current_year + 50:
            errors.append(
                f"Date '{date_str}' in '{field_name}' at line {line_num} in {filename} "
                f"seems unrealistic (year {parsed_date.year})"
            )
    except ValueError:
        errors.append(
            f"Invalid date format '{date_str}' in '{field_name}' at line {line_num} in {filename}. "
            f"Use YYYY-MM-DD"
        )

    return errors


def validate_csv_cross_references() -> list[str]:
    """Validate cross-references between CSV files."""
    errors = []

    try:
        # Load all CSV data for cross-reference validation
        csv_data = {}
        for csv_path in CSV_FILES:
            if csv_path.exists():
                try:
                    with csv_path.open(newline="", encoding="utf-8") as handle:
                        reader = csv.DictReader(handle)
                        csv_data[csv_path.name] = list(reader)
                except (FileNotFoundError, PermissionError, UnicodeDecodeError):
                    continue  # Skip files we can't read

        # Validate project_id references in tasks.csv
        if "tasks.csv" in csv_data and "projects.csv" in csv_data:
            project_ids = {row.get("project_id", "") for row in csv_data["projects.csv"] if row.get("project_id", "").strip()}
            project_ids.add("")  # Empty project_id is valid (no project assigned)

            for i, task in enumerate(csv_data["tasks.csv"], 2):  # Start at line 2 (after header)
                task_project_id = task.get("project_id", "").strip()
                if task_project_id and task_project_id not in project_ids:
                    errors.append(f"Invalid project_id '{task_project_id}' in tasks.csv at line {i} - project does not exist")

        # Validate that goal areas exist in a reasonable set of domains
        if "goals.csv" in csv_data:
            goal_areas = {row.get("area", "").strip().lower() for row in csv_data["goals.csv"] if row.get("area", "").strip()}
            if "tasks.csv" in csv_data:
                task_domains = {row.get("domain", "").strip().lower() for row in csv_data["tasks.csv"] if row.get("domain", "").strip()}
                # Warn if goal areas don't align with task domains (soft validation)
                orphaned_goals = goal_areas - task_domains
                if orphaned_goals and len(orphaned_goals) > 0:
                    # Only warn if there are many orphaned goals (might be intentional)
                    if len(orphaned_goals) > 2:
                        errors.append(f"Many goal areas have no corresponding task domains: {sorted(orphaned_goals)}")

    except Exception as e:
        errors.append(f"Error during cross-reference validation: {e}")

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
            }
        },
        "goals.csv": {
            "required_columns": ["goal_id", "area", "title"],
            "optional_columns": ["horizon", "target_date", "metric_name", "metric_target", "metric_current", "status", "last_updated", "notes"],
            "enums": {
                "horizon": ["quarter", "year", "month"],
                "status": ["active", "completed", "paused", "dropped"]
            }
        },
        "tasks.csv": {
            "required_columns": ["task_id", "title", "domain"],
            "optional_columns": ["project_id", "status", "priority", "effort_mins", "due_date", "energy", "context", "source", "next_step", "scheduled_date", "scheduled_start", "scheduled_end", "last_updated", "notes"],
            "enums": {
                "status": ["queued", "in_progress", "blocked", "completed"],
                "energy": ["low", "medium", "high"],
                "source": ["manual", "auto", "imported"]
            }
        },
        "projects.csv": {
            "required_columns": ["project_id", "area", "name"],
            "optional_columns": ["status", "start_date", "target_date", "description", "last_updated", "notes", "active"],
            "enums": {
                "status": ["planning", "active", "paused", "completed"],
                "active": ["true", "false"]
            }
        },
        "time_blocks.csv": {
            "required_columns": ["block_id", "date", "start", "end", "title"],
            "optional_columns": ["domain", "task_id", "source", "status", "notes"],
            "enums": {
                "source": ["manual", "auto_planner", "imported"],
                "status": ["planned", "in_progress", "completed", "skipped"]
            }
        },
        "time_logs.csv": {
            "required_columns": ["log_id", "date", "start_time", "end_time", "activity"],
            "optional_columns": ["domain", "task_id", "notes", "last_updated"]
        },
        "calendar_events.csv": {
            "required_columns": ["event_id", "date", "start_time", "end_time", "title"],
            "optional_columns": ["location", "attendees", "source", "calendar", "notes"],
            "enums": {
                "source": ["google_calendar", "manual", "outlook"]
            }
        }
    }

    for csv_path in CSV_FILES:
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

                # Validate data rows
                line_num = 2  # Start after header
                for row in reader:
                    # Check required fields are not empty
                    for required_col in schema["required_columns"]:
                        if required_col in row and not row[required_col].strip():
                            errors.append(f"Empty required field '{required_col}' at line {line_num} in {csv_path.relative_to(REPO_ROOT)}")

                    # Validate enums
                    if "enums" in schema:
                        for col, valid_values in schema["enums"].items():
                            if col in row and row[col].strip() and row[col] not in valid_values:
                                errors.append(f"Invalid value '{row[col]}' for '{col}' at line {line_num} in {csv_path.relative_to(REPO_ROOT)}. Valid: {valid_values}")

                    # Validate date formats with enhanced validation
                    for col in ["date", "target_date", "due_date", "start_date", "scheduled_date", "last_updated"]:
                        if col in row and row[col].strip():
                            errors.extend(validate_date_formats_enhanced(
                                row[col], col, line_num, csv_path.relative_to(REPO_ROOT)
                            ))

                    # Validate time formats
                    for col in ["start", "end", "start_time", "end_time", "scheduled_start", "scheduled_end"]:
                        if col in row and row[col].strip():
                            try:
                                datetime.strptime(row[col], "%H:%M")
                            except ValueError:
                                errors.append(f"Invalid time format '{row[col]}' in '{col}' at line {line_num} in {csv_path.relative_to(REPO_ROOT)}. Use HH:MM")

                    line_num += 1

        except (FileNotFoundError, PermissionError, UnicodeDecodeError) as e:
            errors.append(f"Cannot read CSV file {csv_path.relative_to(REPO_ROOT)}: {e}")

    return errors


def validate_markdown_links() -> list[str]:
    errors = []
    for doc_path in markdown_docs():
        content = doc_path.read_text(encoding="utf-8")
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
    errors.extend(validate_config_files())
    errors.extend(validate_file_permissions())
    errors.extend(validate_csv_file_sizes())
    errors.extend(validate_csv_headers())
    errors.extend(validate_csv_structure())
    errors.extend(validate_csv_schemas())
    errors.extend(validate_csv_cross_references())
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
