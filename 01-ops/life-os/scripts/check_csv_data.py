#!/usr/bin/env python3
"""Quick CSV data validation and statistics utility for development."""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

# Paths relative to repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
CANONICAL_DIR = REPO_ROOT / "01-ops" / "life-os" / "data" / "canonical"
LOGS_DIR = REPO_ROOT / "01-ops" / "life-os" / "logs"

# Constants for CSV analysis
LARGE_FILE_THRESHOLD = 1024 * 1024  # 1MB
MAX_SAMPLING_ROWS = 1000
SIZE_THRESHOLD_BYTES = 1024  # 1KB

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^\d{2}:\d{2}$")

# Expected headers and validation rules per CSV file.
# "id_col" is the column used for duplicate detection.
# "required" lists columns that must not be empty.
# "date_cols" / "time_cols" list columns whose non-empty values are validated.
SCHEMAS: Dict[str, Dict[str, Any]] = {
    "tasks.csv": {
        "header": [
            "task_id", "title", "domain", "project_id", "status", "priority",
            "effort_mins", "due_date", "energy", "context", "source",
            "next_step", "scheduled_date", "scheduled_start", "scheduled_end",
            "last_updated", "notes",
        ],
        "id_col": "task_id",
        "required": ["task_id", "title", "domain"],
        "date_cols": ["due_date", "scheduled_date", "last_updated"],
        "time_cols": ["scheduled_start", "scheduled_end"],
    },
    "goals.csv": {
        "header": [
            "goal_id", "area", "title", "horizon", "target_date",
            "metric_name", "metric_target", "metric_current", "status",
            "last_updated", "notes",
        ],
        "id_col": "goal_id",
        "required": ["goal_id", "area", "title"],
        "date_cols": ["target_date", "last_updated"],
        "time_cols": [],
    },
    "habits.csv": {
        "header": [
            "habit_id", "area", "name", "frequency", "target_per_week",
            "min_value", "unit", "active", "notes", "last_updated",
        ],
        "id_col": "habit_id",
        "required": [
            "habit_id", "area", "name", "frequency", "target_per_week",
            "min_value", "unit", "active",
        ],
        "date_cols": ["last_updated"],
        "time_cols": [],
    },
    "projects.csv": {
        "header": [
            "project_id", "area", "name", "status", "start_date",
            "target_date", "description", "last_updated", "notes", "active",
        ],
        "id_col": "project_id",
        "required": ["project_id", "area", "name"],
        "date_cols": ["start_date", "target_date", "last_updated"],
        "time_cols": [],
    },
    "calendar_events.csv": {
        "header": [
            "event_id", "date", "start_time", "end_time", "title",
            "location", "attendees", "source", "calendar", "notes",
        ],
        "id_col": "event_id",
        "required": ["event_id", "date", "start_time", "end_time", "title"],
        "date_cols": ["date"],
        "time_cols": ["start_time", "end_time"],
    },
    "time_blocks.csv": {
        "header": [
            "block_id", "date", "start", "end", "title", "domain",
            "task_id", "source", "status", "notes",
        ],
        "id_col": "block_id",
        "required": ["block_id", "date", "start", "end", "title"],
        "date_cols": ["date"],
        "time_cols": ["start", "end"],
    },
    "time_logs.csv": {
        "header": [
            "log_id", "date", "start_time", "end_time", "activity",
            "domain", "duration_mins", "task_id", "notes",
        ],
        "id_col": "log_id",
        "required": ["log_id", "date", "start_time", "end_time", "activity"],
        "date_cols": ["date"],
        "time_cols": ["start_time", "end_time"],
    },
}


def _init_csv_stats(csv_path: Path) -> dict:
    """Initialize stats dictionary for CSV analysis."""
    return {
        "file": csv_path.relative_to(REPO_ROOT),
        "exists": csv_path.exists(),
        "rows": 0,
        "columns": 0,
        "has_data": False,
        "sample_row": None,
        "size_bytes": 0,
    }


def _process_large_csv(reader: Any, stats: dict) -> dict:
    """Process large CSV files with sampling to avoid memory issues."""
    row_count = 0
    sample_row = None

    for row in reader:
        row_count += 1
        if row_count == 1:
            sample_row = row
        if row_count > MAX_SAMPLING_ROWS:
            stats["rows"] = f"{row_count}+ (large file, sampling)"
            stats["has_data"] = True
            stats["sample_row"] = sample_row
            return stats

    stats["rows"] = row_count
    stats["has_data"] = row_count > 0
    stats["sample_row"] = sample_row
    return stats


def _process_small_csv(reader: Any, stats: dict) -> dict:
    """Process small CSV files by loading all data."""
    data_rows = list(reader)
    stats["rows"] = len(data_rows)
    stats["has_data"] = len(data_rows) > 0
    if data_rows:
        stats["sample_row"] = data_rows[0]
    return stats


def analyze_csv_file(csv_path: Path) -> dict:
    """Analyze a single CSV file and return stats."""
    stats = _init_csv_stats(csv_path)

    if not csv_path.exists():
        return stats

    try:
        # Get file size for performance context
        stats["size_bytes"] = csv_path.stat().st_size

        with csv_path.open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            try:
                header = next(reader, None)
            except UnicodeDecodeError as e:
                stats["error"] = f"Encoding error: {e}"
                return stats

            if header:
                stats["columns"] = len(header)
                stats["header"] = header

                # For performance, avoid loading all data for large files
                if stats["size_bytes"] > LARGE_FILE_THRESHOLD:
                    stats = _process_large_csv(reader, stats)
                else:
                    stats = _process_small_csv(reader, stats)

    except PermissionError:
        stats["error"] = "Permission denied"
    except (OSError, UnicodeDecodeError, csv.Error) as e:
        error_msg = f"Unexpected error: {type(e).__name__}: {e}"
        stats["error"] = error_msg

    return stats


def validate_csv_file(csv_path: Path) -> List[str]:
    """Validate a CSV file against its schema. Returns a list of error strings."""
    errors: List[str] = []
    filename = csv_path.name
    schema = SCHEMAS.get(filename)
    if schema is None:
        return errors  # no schema defined, skip validation

    if not csv_path.exists():
        errors.append(f"{filename}: file not found")
        return errors

    try:
        with csv_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                errors.append(f"{filename}: empty file, no header row")
                return errors

            actual = list(reader.fieldnames)
            expected = schema["header"]
            if actual != expected:
                errors.append(
                    f"{filename}: header mismatch — got {actual}, expected {expected}"
                )
                return errors  # can't validate rows if header is wrong

            id_col: str = schema["id_col"]
            required: List[str] = schema["required"]
            date_cols: List[str] = schema["date_cols"]
            time_cols: List[str] = schema["time_cols"]

            seen_ids: Set[str] = set()
            for row_num, row in enumerate(reader, start=2):
                row_id = row.get(id_col, "")

                # Duplicate ID check
                if row_id:
                    if row_id in seen_ids:
                        errors.append(
                            f"{filename}:{row_num}: duplicate {id_col} '{row_id}'"
                        )
                    seen_ids.add(row_id)

                # Required fields
                for col in required:
                    if not row.get(col, "").strip():
                        errors.append(
                            f"{filename}:{row_num}: required field '{col}' is empty"
                        )

                # Date format
                for col in date_cols:
                    val = row.get(col, "").strip()
                    if val and not DATE_RE.match(val):
                        errors.append(
                            f"{filename}:{row_num}: invalid date in '{col}': '{val}'"
                        )

                # Time format
                for col in time_cols:
                    val = row.get(col, "").strip()
                    if val and not TIME_RE.match(val):
                        errors.append(
                            f"{filename}:{row_num}: invalid time in '{col}': '{val}'"
                        )

    except (OSError, csv.Error) as e:
        errors.append(f"{filename}: read error — {e}")

    return errors


def main() -> int:
    """Analyze all CSV files and print summary."""
    print("CSV Data Analysis")
    print("=" * 50)

    all_files = [
        CANONICAL_DIR / "tasks.csv",
        CANONICAL_DIR / "habits.csv",
        CANONICAL_DIR / "goals.csv",
        CANONICAL_DIR / "projects.csv",
        CANONICAL_DIR / "time_blocks.csv",
        CANONICAL_DIR / "time_logs.csv",
        CANONICAL_DIR / "calendar_events.csv",
        LOGS_DIR / "daily_log.csv",
        LOGS_DIR / "activity_log.csv",
    ]

    for csv_file in all_files:
        stats = analyze_csv_file(csv_file)

        print(f"\n📄 {stats['file']}")
        if not stats["exists"]:
            print("   ❌ File not found")
            continue

        if "error" in stats:
            print(f"   ⚠️  Error: {stats['error']}")
            continue

        # Format file size for display
        size_str = ""
        if stats["size_bytes"] > 0:
            if stats["size_bytes"] < SIZE_THRESHOLD_BYTES:
                size_str = f" ({stats['size_bytes']} bytes)"
            else:
                size_kb = stats["size_bytes"] / 1024
                size_str = f" ({size_kb:.1f}KB)"

        print(f"   📊 {stats['columns']} columns, {stats['rows']} data rows{size_str}")

        if stats["has_data"]:
            sample_preview = stats["sample_row"][:2] if stats["sample_row"] else "None"
            print(f"   ✅ Has data (sample: {sample_preview}...)")
        else:
            print("   📝 Header only (no data)")

    # Validation pass
    print("\n" + "=" * 50)
    print("\nCSV Validation")
    print("=" * 50)

    all_errors: List[str] = []
    for csv_file in all_files:
        file_errors = validate_csv_file(csv_file)
        if file_errors:
            all_errors.extend(file_errors)
            for err in file_errors:
                print(f"   ❌ {err}")
        elif csv_file.exists() and csv_file.name in SCHEMAS:
            print(f"   ✅ {csv_file.name} — valid")

    print("\n" + "=" * 50)
    if all_errors:
        print(f"Validation found {len(all_errors)} error(s).")
    else:
        print("All CSV files valid.")

    return len(all_errors)


if __name__ == "__main__":
    sys.exit(main())
