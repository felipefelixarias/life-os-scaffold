#!/usr/bin/env python3
"""
Utility functions and common operations for life-os scripts.

This module provides shared functionality used across multiple life-os
scripts, including CSV operations, date handling, and logging utilities.
"""

import csv
import logging
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Common paths
REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "01-ops" / "life-os" / "data" / "canonical"
LOGS_DIR = REPO_ROOT / "01-ops" / "life-os" / "logs"
CONFIG_DIR = REPO_ROOT / "01-ops" / "life-os" / "config"
OUTPUTS_DIR = REPO_ROOT / "01-ops" / "life-os" / "outputs"

# Ensure critical directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


def setup_logging(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Set up logging with consistent formatting across life-os scripts.

    Args:
        name: Logger name (typically __name__)
        level: Logging level (default: INFO)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Avoid duplicate handlers if already configured
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # Console handler with colored output
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    return logger


def read_csv(file_path: Union[str, Path], required: bool = True) -> List[Dict[str, str]]:
    """
    Read a CSV file and return list of dictionaries.

    Args:
        file_path: Path to the CSV file
        required: If True, raise exception if file doesn't exist

    Returns:
        List of dictionaries representing CSV rows

    Raises:
        FileNotFoundError: If required=True and file doesn't exist
    """
    path = Path(file_path)

    if not path.exists():
        if required:
            raise FileNotFoundError(f"Required CSV file not found: {path}")
        return []

    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            return list(reader)
    except (PermissionError, UnicodeDecodeError) as e:
        logger = setup_logging(__name__)
        logger.error(f"Error reading CSV file {path}: {e}")
        if required:
            raise
        return []


def write_csv(
    file_path: Union[str, Path],
    data: List[Dict[str, str]],
    fieldnames: Optional[List[str]] = None
) -> bool:
    """
    Write data to a CSV file.

    Args:
        file_path: Path to write the CSV file
        data: List of dictionaries to write
        fieldnames: Column names (auto-detected if None)

    Returns:
        True if successful, False otherwise
    """
    if not data:
        return False

    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if fieldnames is None:
        fieldnames = list(data[0].keys())

    try:
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        return True
    except (PermissionError, OSError) as e:
        logger = setup_logging(__name__)
        logger.error(f"Error writing CSV file {path}: {e}")
        return False


def append_csv_row(file_path: Union[str, Path], row: Dict[str, str]) -> bool:
    """
    Append a single row to a CSV file, creating it if necessary.

    Args:
        file_path: Path to the CSV file
        row: Dictionary representing the row to append

    Returns:
        True if successful, False otherwise
    """
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # If file doesn't exist, create it with the header
    if not path.exists():
        return write_csv(path, [row])

    try:
        # Read existing file to get fieldnames
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames

        # Append the row
        with path.open("a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writerow(row)
        return True
    except (PermissionError, OSError, UnicodeDecodeError) as e:
        logger = setup_logging(__name__)
        logger.error(f"Error appending to CSV file {path}: {e}")
        return False


def validate_date_string(date_str: str, allow_empty: bool = True) -> Optional[date]:
    """
    Validate and parse a date string in YYYY-MM-DD format.

    Args:
        date_str: Date string to validate
        allow_empty: Whether to allow empty strings

    Returns:
        Parsed date object, or None if invalid/empty
    """
    if not date_str.strip():
        return None if allow_empty else date.today()

    try:
        return datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def format_date(d: Union[date, datetime, str, None]) -> str:
    """
    Format a date as YYYY-MM-DD string.

    Args:
        d: Date to format (date, datetime, or string)

    Returns:
        Formatted date string or empty string if invalid
    """
    if d is None:
        return ""

    if isinstance(d, str):
        parsed = validate_date_string(d)
        return parsed.isoformat() if parsed else ""

    if isinstance(d, datetime):
        return d.date().isoformat()

    if isinstance(d, date):
        return d.isoformat()

    return ""


def get_today_string() -> str:
    """Get today's date as YYYY-MM-DD string."""
    return date.today().isoformat()


def safe_get(data: Dict[str, Any], key: str, default: str = "") -> str:
    """
    Safely get a value from a dictionary, ensuring string return.

    Args:
        data: Dictionary to get value from
        key: Key to look up
        default: Default value if key missing or value is None

    Returns:
        String value or default
    """
    value = data.get(key, default)
    return str(value) if value is not None else default


def log_activity(event: str, details: str = "") -> bool:
    """
    Log an activity to the activity log CSV.

    Args:
        event: Type of event (e.g., "task_completed", "habit_tracked")
        details: Additional details about the event

    Returns:
        True if logged successfully, False otherwise
    """
    activity_log_path = LOGS_DIR / "activity_log.csv"

    row = {
        "timestamp": datetime.now().isoformat(),
        "event": event,
        "details": details
    }

    return append_csv_row(activity_log_path, row)


def get_csv_files() -> List[Path]:
    """Get list of all CSV files in the canonical data directory."""
    return sorted(DATA_DIR.glob("*.csv")) + sorted(LOGS_DIR.glob("*.csv"))


def backup_csv_file(file_path: Union[str, Path]) -> Optional[Path]:
    """
    Create a timestamped backup of a CSV file.

    Args:
        file_path: Path to the CSV file to backup

    Returns:
        Path to backup file if successful, None otherwise
    """
    path = Path(file_path)

    if not path.exists():
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.parent / f"{path.stem}_{timestamp}.backup{path.suffix}"

    try:
        import shutil
        shutil.copy2(path, backup_path)
        return backup_path
    except (OSError, ImportError) as e:
        logger = setup_logging(__name__)
        logger.error(f"Error creating backup of {path}: {e}")
        return None