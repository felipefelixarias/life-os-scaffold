#!/usr/bin/env python3
"""Quick CSV data validation and statistics utility for development."""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Dict, List, Optional

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
    }

    if not csv_path.exists():
        return stats

    try:
        with csv_path.open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)

            if header:
                stats["columns"] = len(header)
                stats["header"] = header

                # Count data rows and get a sample
                data_rows = list(reader)
                stats["rows"] = len(data_rows)
                stats["has_data"] = len(data_rows) > 0

                if data_rows:
                    stats["sample_row"] = data_rows[0]

    except Exception as e:
        stats["error"] = str(e)

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

        print(f"   📊 {stats['columns']} columns, {stats['rows']} data rows")

        if stats["has_data"]:
            print(f"   ✅ Has data (sample: {stats['sample_row'][:2] if stats['sample_row'] else 'None'}...)")
        else:
            print("   📝 Header only (no data)")

    print("\n" + "=" * 50)
    print("Analysis complete. Use this during development to check CSV state.")


if __name__ == "__main__":
    main()