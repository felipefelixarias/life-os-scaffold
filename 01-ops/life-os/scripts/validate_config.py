"""Configuration file validation for life-os profile and calendar feeds."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"

VALID_ENERGY_LEVELS = {"low", "medium", "high"}
VALID_WEEKDAYS = {
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
}

# Fields that must be HH:MM time strings
_PLANNING_TIME_FIELDS = {
    "weekday_wake",
    "weekend_earliest",
    "day_end",
    "bedtime",
    "workday_commute_start",
    "workday_start",
    "workday_end",
    "workday_commute_home_end",
}

# Fields that must be positive integers
_PLANNING_INT_FIELDS = {
    "default_task_block_mins",
    "deep_work_block_mins",
    "max_screen_block_mins",
    "break_mins",
    "max_major_tasks_per_day",
}


def _is_valid_time(value: str) -> bool:
    """Check if a string is a valid HH:MM time."""
    try:
        datetime.strptime(value, "%H:%M")
        return True
    except (ValueError, TypeError):
        return False


def _check_type(
    data: dict[str, Any],
    key: str,
    expected_type: type,
    context: str,
) -> list[str]:
    """Check that a key exists and has the expected type."""
    if key not in data:
        return [f"{context}: missing required field '{key}'"]
    if not isinstance(data[key], expected_type):
        return [
            f"{context}: '{key}' should be {expected_type.__name__}, "
            f"got {type(data[key]).__name__}"
        ]
    return []


def validate_profile(data: dict[str, Any]) -> list[str]:
    """Validate a profile configuration dict. Returns list of errors."""
    errors: list[str] = []

    # Top-level required fields
    errors.extend(_check_type(data, "owner", str, "profile"))
    errors.extend(_check_type(data, "timezone", str, "profile"))

    # Planning section
    errors.extend(_check_type(data, "planning", dict, "profile"))
    if isinstance(data.get("planning"), dict):
        planning = data["planning"]

        for field in _PLANNING_TIME_FIELDS:
            if field not in planning:
                errors.append(f"profile.planning: missing required field '{field}'")
            elif not isinstance(planning[field], str) or not _is_valid_time(
                planning[field]
            ):
                errors.append(
                    f"profile.planning: '{field}' must be a valid HH:MM time, "
                    f"got '{planning[field]}'"
                )

        for field in _PLANNING_INT_FIELDS:
            if field not in planning:
                errors.append(f"profile.planning: missing required field '{field}'")
            elif not isinstance(planning[field], int) or planning[field] <= 0:
                errors.append(
                    f"profile.planning: '{field}' must be a positive integer, "
                    f"got '{planning[field]}'"
                )

        if (
            "weekly_review_day" in planning
            and planning["weekly_review_day"] not in VALID_WEEKDAYS
        ):
            errors.append(
                f"profile.planning: 'weekly_review_day' must be a weekday name, "
                f"got '{planning['weekly_review_day']}'"
            )

    # Domains
    errors.extend(_check_type(data, "domains", list, "profile"))
    if isinstance(data.get("domains"), list):
        for i, domain in enumerate(data["domains"]):
            ctx = f"profile.domains[{i}]"
            if not isinstance(domain, dict):
                errors.append(f"{ctx}: expected object, got {type(domain).__name__}")
                continue
            for field in ("id", "name"):
                errors.extend(_check_type(domain, field, str, ctx))
            if "weight" in domain and (
                not isinstance(domain["weight"], (int, float)) or domain["weight"] < 0
            ):
                errors.append(f"{ctx}: 'weight' must be a non-negative number")

    # Energy curve
    errors.extend(_check_type(data, "energy_curve", list, "profile"))
    if isinstance(data.get("energy_curve"), list):
        for i, entry in enumerate(data["energy_curve"]):
            ctx = f"profile.energy_curve[{i}]"
            if not isinstance(entry, dict):
                errors.append(f"{ctx}: expected object, got {type(entry).__name__}")
                continue
            if "time" not in entry:
                errors.append(f"{ctx}: missing required field 'time'")
            elif not _is_valid_time(entry["time"]):
                errors.append(
                    f"{ctx}: 'time' must be a valid HH:MM time, got '{entry['time']}'"
                )
            if "energy" not in entry:
                errors.append(f"{ctx}: missing required field 'energy'")
            elif entry["energy"] not in VALID_ENERGY_LEVELS:
                errors.append(
                    f"{ctx}: 'energy' must be one of {sorted(VALID_ENERGY_LEVELS)}, "
                    f"got '{entry['energy']}'"
                )

    # Priority tiers (optional but validated if present)
    if "priority_tiers" in data:
        if not isinstance(data["priority_tiers"], list):
            errors.append(
                f"profile: 'priority_tiers' should be list, "
                f"got {type(data['priority_tiers']).__name__}"
            )
        else:
            for i, tier in enumerate(data["priority_tiers"]):
                ctx = f"profile.priority_tiers[{i}]"
                if not isinstance(tier, dict):
                    errors.append(f"{ctx}: expected object, got {type(tier).__name__}")
                    continue
                if "tier" in tier and (
                    not isinstance(tier["tier"], int) or tier["tier"] < 1
                ):
                    errors.append(f"{ctx}: 'tier' must be a positive integer")
                errors.extend(_check_type(tier, "label", str, ctx))

    return errors


def validate_calendar_feeds(data: dict[str, Any]) -> list[str]:
    """Validate a calendar_feeds configuration dict. Returns list of errors."""
    errors: list[str] = []

    errors.extend(_check_type(data, "feeds", list, "calendar_feeds"))
    if not isinstance(data.get("feeds"), list):
        return errors

    for i, feed in enumerate(data["feeds"]):
        ctx = f"calendar_feeds.feeds[{i}]"
        if not isinstance(feed, dict):
            errors.append(f"{ctx}: expected object, got {type(feed).__name__}")
            continue
        for field in ("name", "url", "output_file"):
            errors.extend(_check_type(feed, field, str, ctx))
        if "enabled" in feed and not isinstance(feed["enabled"], bool):
            errors.append(f"{ctx}: 'enabled' must be a boolean")
        if "timeout_seconds" in feed:
            val = feed["timeout_seconds"]
            if not isinstance(val, (int, float)) or val <= 0:
                errors.append(f"{ctx}: 'timeout_seconds' must be a positive number")

    return errors


def validate_config_file(filepath: Path) -> list[str]:
    """Load and validate a JSON config file. Returns list of errors."""
    errors: list[str] = []

    if not filepath.exists():
        return [f"File not found: {filepath}"]

    try:
        with filepath.open(encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return [f"Invalid JSON in {filepath.name}: {e}"]

    if not isinstance(data, dict):
        return [f"{filepath.name}: expected a JSON object at top level"]

    name = filepath.stem
    if name == "profile" or name == "profile.example":
        errors.extend(validate_profile(data))
    elif name == "calendar_feeds" or name == "calendar_feeds.example":
        errors.extend(validate_calendar_feeds(data))
    else:
        errors.append(f"No validation schema for config file: {filepath.name}")

    return errors


def validate_all_configs(config_dir: Path | None = None) -> dict[str, list[str]]:
    """Validate all config files in the config directory. Returns dict of filename -> errors."""
    if config_dir is None:
        config_dir = CONFIG_DIR

    results: dict[str, list[str]] = {}
    for filepath in sorted(config_dir.glob("*.json")):
        results[filepath.name] = validate_config_file(filepath)
    return results
