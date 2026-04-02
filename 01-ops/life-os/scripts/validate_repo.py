#!/usr/bin/env python3
"""Repo-local validation and lint checks for the life-os scaffold."""

from __future__ import annotations

import argparse
import csv
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

# Configure basic logging
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


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
    """Print an error message with consistent formatting."""
    print(f"ERROR: {message}")


def validate_required_paths() -> list[str]:
    """Validate that all required directories and files exist."""
    paths = [
        REPO_ROOT / ".claude" / "commands",
        REPO_ROOT / "01-ops" / "life-os" / "config" / "profile.example.json",
        REPO_ROOT / "01-ops" / "life-os" / "config" / "calendar_feeds.example.json",
        REPO_ROOT / "01-ops" / "life-os" / "scripts" / "gcal.py",
    ]
    errors = [
        f"Missing required path: {path.relative_to(REPO_ROOT)}"
        for path in paths
        if not path.exists()
    ]
    return errors


def validate_csv_headers() -> list[str]:
    """Validate CSV file headers for basic integrity and formatting."""
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
    """Validate CSV file structure for consistency."""
    errors = []
    for csv_path in csv_files():
        try:
            with csv_path.open(newline="", encoding="utf-8") as handle:
                reader = csv.reader(handle)
                header = next(reader, None)
                if not header:
                    continue

                header_count = len(header)
                line_num = 2  # Start after header
                max_lines_to_check = 1000  # Limit for performance on large files

                for row_idx, row in enumerate(reader):
                    if len(row) != header_count:
                        errors.append(
                            f"CSV row mismatch at line {line_num} in {csv_path.relative_to(REPO_ROOT)}: "
                            f"expected {header_count} columns, got {len(row)}"
                        )
                        break  # Stop after first mismatch to avoid noise
                    line_num += 1

                    # Performance optimization: don't check infinite rows
                    if row_idx >= max_lines_to_check:
                        logger.info(f"Checked first {max_lines_to_check} rows of {csv_path.relative_to(REPO_ROOT)}")
                        break

        except (FileNotFoundError, PermissionError, UnicodeDecodeError):
            # Already handled in validate_csv_headers
            pass

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
            "optional_columns": ["domain", "duration_mins", "task_id", "notes", "last_updated"]
        },
        "calendar_events.csv": {
            "required_columns": ["event_id", "date", "start_time", "end_time", "title"],
            "optional_columns": ["location", "attendees", "source", "calendar", "notes"],
            "enums": {
                "source": ["google_calendar", "manual", "outlook"]
            }
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
                errors.extend(
                    f"Missing required column '{required_col}' in {csv_path.relative_to(REPO_ROOT)}"
                    for required_col in schema["required_columns"]
                    if required_col not in header
                )

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

                    # Validate date formats
                    for col in DATE_COLUMNS:
                        if col in row and row[col].strip():
                            try:
                                datetime.strptime(row[col], "%Y-%m-%d")
                            except ValueError:
                                errors.append(f"Invalid date format '{row[col]}' in '{col}' at line {line_num} in {csv_path.relative_to(REPO_ROOT)}. Use YYYY-MM-DD")

                    # Validate time formats
                    for col in TIME_COLUMNS:
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
    """Validate that all relative links in markdown files resolve to existing files."""
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
    """Validate that command references in documentation point to existing command files."""
    command_dir = REPO_ROOT / ".claude" / "commands"
    defined = {f"/{path.stem}" for path in command_dir.glob("*.md")}
    errors = []
    for doc_path in command_reference_docs():
        content = doc_path.read_text(encoding="utf-8")
        errors.extend(
            f"Unknown command reference in {doc_path.relative_to(REPO_ROOT)}: {command}"
            for command in COMMAND_RE.findall(content)
            if command not in defined
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
    """Check for trailing whitespace in markdown files and command files."""
    errors = []
    paths = markdown_docs() + sorted((REPO_ROOT / ".claude" / "commands").glob("*.md"))
    for path in paths:
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.endswith(" ") or line.endswith("\t"):
                errors.append(f"Trailing whitespace in {path.relative_to(REPO_ROOT)}:{line_no}")
    return errors


def main() -> int:
    """Main entry point for the validation script with optional lint checks."""
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
