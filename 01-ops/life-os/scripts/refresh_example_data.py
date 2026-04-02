#!/usr/bin/env python3
"""Refresh CSV files with minimal example data for testing and onboarding."""

from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "01-ops" / "life-os" / "data" / "canonical"
LOGS_DIR = REPO_ROOT / "01-ops" / "life-os" / "logs"


def ensure_directory(path: Path) -> None:
    """Ensure directory exists."""
    path.mkdir(parents=True, exist_ok=True)


def write_csv_with_example(file_path: Path, headers: list[str], example_rows: list[list[str]]) -> None:
    """Write a CSV file with headers and example data."""
    with file_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(example_rows)
    print(f"✅ Updated {file_path.relative_to(REPO_ROOT)}")


def refresh_canonical_csvs() -> None:
    """Refresh all canonical CSV files with minimal example data."""
    ensure_directory(DATA_DIR)

    today = date.today()
    tomorrow = today + timedelta(days=1)

    # Tasks CSV
    write_csv_with_example(
        DATA_DIR / "tasks.csv",
        ["task_id", "title", "domain", "project_id", "status", "priority",
         "effort_mins", "due_date", "energy", "context", "source", "next_step",
         "scheduled_date", "scheduled_start", "scheduled_end", "last_updated", "notes"],
        [["example_task", "Review quarterly goals", "planning", "", "queued", "medium",
          "30", "", "medium", "desk", "manual", "Open goals document",
          "", "", "", today.isoformat(), "Example task for testing"]]
    )

    # Habits CSV
    write_csv_with_example(
        DATA_DIR / "habits.csv",
        ["habit_id", "area", "name", "frequency", "target_per_week", "min_value",
         "unit", "active", "notes", "last_updated"],
        [
            ["sleep_7h", "health", "Sleep 7+ hours", "daily", "7", "7", "hours", "true", "Consistent sleep schedule", today.isoformat()],
            ["exercise", "health", "Exercise", "daily", "5", "1", "session", "true", "Any physical activity", today.isoformat()],
            ["water", "health", "Drink water", "daily", "7", "8", "glasses", "true", "Stay hydrated", today.isoformat()],
            ["read", "growth", "Read", "daily", "4", "15", "minutes", "true", "Daily reading habit", today.isoformat()],
            ["meditate", "health", "Meditate", "daily", "5", "10", "minutes", "true", "Mindfulness practice", today.isoformat()],
        ]
    )

    # Goals CSV
    write_csv_with_example(
        DATA_DIR / "goals.csv",
        ["goal_id", "area", "title", "horizon", "target_date", "metric_name",
         "metric_target", "metric_current", "status", "last_updated", "notes"],
        [["example_goal", "health", "Establish consistent sleep routine", "quarter",
          tomorrow.isoformat(), "days_with_7h_sleep", "90", "0", "active",
          today.isoformat(), "Improve sleep quality and consistency"]]
    )

    # Projects CSV
    write_csv_with_example(
        DATA_DIR / "projects.csv",
        ["project_id", "area", "name", "status", "start_date", "target_date",
         "description", "last_updated", "notes", "active"],
        [["example_project", "health", "Morning routine optimization", "planning",
          today.isoformat(), "", "Streamline and improve morning routine",
          today.isoformat(), "Focus on consistency and energy", "true"]]
    )

    # Time blocks CSV
    write_csv_with_example(
        DATA_DIR / "time_blocks.csv",
        ["block_id", "date", "start", "end", "title", "domain", "task_id",
         "source", "status", "notes"],
        [["example_block", today.isoformat(), "09:00", "10:00", "Deep work",
          "work", "", "manual", "planned", "Focus time for important tasks"]]
    )

    # Time logs CSV
    write_csv_with_example(
        DATA_DIR / "time_logs.csv",
        ["log_id", "date", "start_time", "end_time", "activity", "domain",
         "duration_mins", "task_id", "notes"],
        [["example_log", today.isoformat(), "09:00", "10:00", "Project planning",
          "work", "60", "", "Morning planning session"]]
    )

    # Calendar events CSV
    write_csv_with_example(
        DATA_DIR / "calendar_events.csv",
        ["event_id", "date", "start_time", "end_time", "title", "location",
         "attendees", "source", "calendar", "notes"],
        [["example_event", today.isoformat(), "14:00", "15:00", "Team meeting",
          "Conference Room A", "team@company.com", "manual", "primary", "Weekly sync"]]
    )


def refresh_log_csvs() -> None:
    """Refresh log CSV files with minimal example data."""
    ensure_directory(LOGS_DIR)

    today = date.today()

    # Daily log CSV
    write_csv_with_example(
        LOGS_DIR / "daily_log.csv",
        ["date", "habit_id", "value", "notes"],
        [[today.isoformat(), "sleep_7h", "7.5", "Good night's sleep"]]
    )

    # Activity log CSV
    write_csv_with_example(
        LOGS_DIR / "activity_log.csv",
        ["timestamp", "activity", "notes"],
        [[f"{today.isoformat()}T09:00:00Z", "system_setup", "Initial repository setup"]]
    )


def main() -> None:
    """Refresh all CSV files with example data."""
    print("Refreshing CSV files with example data...")
    print("=" * 50)

    refresh_canonical_csvs()
    refresh_log_csvs()

    print("=" * 50)
    print("✅ All CSV files refreshed with example data")
    print("These files are safe to commit and provide good starting examples.")


if __name__ == "__main__":
    main()