#!/usr/bin/env python3
"""Quick CSV data validation and statistics utility for development."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict

# Paths relative to repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
CANONICAL_DIR = REPO_ROOT / "01-ops" / "life-os" / "data" / "canonical"
LOGS_DIR = REPO_ROOT / "01-ops" / "life-os" / "logs"


def analyze_csv_file(csv_path: Path) -> Dict:
    """Analyze a single CSV file and return stats."""
    stats = {
        "file": csv_path.relative_to(REPO_ROOT),
        "exists": csv_path.exists(),
        "rows": 0,
        "columns": 0,
        "has_data": False,
        "sample_row": None,
        "size_bytes": 0,
    }

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
                if stats["size_bytes"] > 1024 * 1024:  # 1MB
                    # Sample approach for large files
                    row_count = 0
                    sample_row = None
                    for row in reader:
                        row_count += 1
                        if row_count == 1:
                            sample_row = row
                        if row_count > 1000:  # Stop early for very large files
                            stats["rows"] = f"{row_count}+ (large file, sampling)"
                            stats["has_data"] = True
                            stats["sample_row"] = sample_row
                            return stats
                    stats["rows"] = row_count
                    stats["has_data"] = row_count > 0
                    stats["sample_row"] = sample_row
                else:
                    # Load all data for smaller files
                    data_rows = list(reader)
                    stats["rows"] = len(data_rows)
                    stats["has_data"] = len(data_rows) > 0
                    if data_rows:
                        stats["sample_row"] = data_rows[0]

    except PermissionError:
        stats["error"] = "Permission denied"
    except Exception as e:
        stats["error"] = f"Unexpected error: {type(e).__name__}: {e}"

    return stats


def main() -> None:
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
            if stats["size_bytes"] < 1024:
                size_str = f" ({stats['size_bytes']} bytes)"
            else:
                size_kb = stats["size_bytes"] / 1024
                size_str = f" ({size_kb:.1f}KB)"

        print(f"   📊 {stats['columns']} columns, {stats['rows']} data rows{size_str}")

        if stats["has_data"]:
            print(f"   ✅ Has data (sample: {stats['sample_row'][:2] if stats['sample_row'] else 'None'}...)")
        else:
            print("   📝 Header only (no data)")

    print("\n" + "=" * 50)
    print("Analysis complete. Use this during development to check CSV state.")


if __name__ == "__main__":
    main()