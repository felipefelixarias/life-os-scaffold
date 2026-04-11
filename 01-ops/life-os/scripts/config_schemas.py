"""Configuration file schema definitions and validation for life-os."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass
class FieldSchema:
    """Schema definition for a single JSON field."""

    name: str
    required: bool = True
    dtype: str = "str"  # str, int, float, bool, list, dict, time, timezone, url
    nullable: bool = False
    enum_values: list[str] = field(default_factory=list)
    min_value: float | None = None
    max_value: float | None = None
    children: list[FieldSchema] = field(default_factory=list)  # for dict items
    item_schema: list[FieldSchema] = field(default_factory=list)  # for list items


@dataclass
class ConfigSchema:
    """Schema definition for a JSON configuration file."""

    name: str
    fields: list[FieldSchema]


TIME_RE_PATTERN = r"^\d{2}:\d{2}$"

PROFILE_SCHEMA = ConfigSchema(
    name="profile",
    fields=[
        FieldSchema("owner", required=True, dtype="str"),
        FieldSchema("timezone", required=True, dtype="timezone"),
        FieldSchema(
            "planning",
            required=True,
            dtype="dict",
            children=[
                FieldSchema("weekday_wake", required=True, dtype="time"),
                FieldSchema("weekend_earliest", required=True, dtype="time"),
                FieldSchema("day_end", required=True, dtype="time"),
                FieldSchema("bedtime", required=True, dtype="time"),
                FieldSchema("workday_commute_start", required=False, dtype="time"),
                FieldSchema("workday_start", required=False, dtype="time"),
                FieldSchema("workday_end", required=False, dtype="time"),
                FieldSchema("workday_commute_home_end", required=False, dtype="time"),
                FieldSchema(
                    "default_task_block_mins",
                    required=False,
                    dtype="int",
                    min_value=1,
                    max_value=480,
                ),
                FieldSchema(
                    "deep_work_block_mins",
                    required=False,
                    dtype="int",
                    min_value=1,
                    max_value=480,
                ),
                FieldSchema(
                    "max_screen_block_mins",
                    required=False,
                    dtype="int",
                    min_value=1,
                    max_value=480,
                ),
                FieldSchema(
                    "break_mins",
                    required=False,
                    dtype="int",
                    min_value=1,
                    max_value=120,
                ),
                FieldSchema(
                    "max_major_tasks_per_day",
                    required=False,
                    dtype="int",
                    min_value=1,
                    max_value=20,
                ),
                FieldSchema(
                    "weekly_review_day",
                    required=False,
                    dtype="enum",
                    enum_values=[
                        "Monday",
                        "Tuesday",
                        "Wednesday",
                        "Thursday",
                        "Friday",
                        "Saturday",
                        "Sunday",
                    ],
                ),
            ],
        ),
        FieldSchema(
            "domains",
            required=True,
            dtype="list",
            item_schema=[
                FieldSchema("id", required=True, dtype="str"),
                FieldSchema("name", required=True, dtype="str"),
                FieldSchema(
                    "weight", required=True, dtype="int", min_value=1, max_value=10
                ),
            ],
        ),
        FieldSchema(
            "energy_curve",
            required=True,
            dtype="list",
            item_schema=[
                FieldSchema("time", required=True, dtype="time"),
                FieldSchema(
                    "energy",
                    required=True,
                    dtype="enum",
                    enum_values=["low", "medium", "high"],
                ),
            ],
        ),
        FieldSchema(
            "priority_tiers",
            required=True,
            dtype="list",
            item_schema=[
                FieldSchema("tier", required=True, dtype="int", min_value=1),
                FieldSchema("label", required=True, dtype="str"),
                FieldSchema("examples", required=True, dtype="str"),
            ],
        ),
    ],
)

CALENDAR_FEEDS_SCHEMA = ConfigSchema(
    name="calendar_feeds",
    fields=[
        FieldSchema(
            "feeds",
            required=True,
            dtype="list",
            item_schema=[
                FieldSchema("name", required=True, dtype="str"),
                FieldSchema("enabled", required=True, dtype="bool"),
                FieldSchema("url", required=True, dtype="url"),
                FieldSchema("output_file", required=True, dtype="str"),
                FieldSchema("timeout_seconds", dtype="int", min_value=1, max_value=300),
            ],
        ),
    ],
)

SCHEMAS: dict[str, ConfigSchema] = {
    "profile": PROFILE_SCHEMA,
    "calendar_feeds": CALENDAR_FEEDS_SCHEMA,
}


def _validate_time(value: str) -> bool:
    """Check if value is a valid HH:MM time string."""
    import re

    if not re.match(TIME_RE_PATTERN, value):
        return False
    parts = value.split(":")
    h, m = int(parts[0]), int(parts[1])
    return 0 <= h <= 23 and 0 <= m <= 59


def _validate_timezone(value: str) -> bool:
    """Check if value is a valid IANA timezone."""
    try:
        ZoneInfo(value)
        return True
    except (ZoneInfoNotFoundError, KeyError):
        return False


def _validate_url(value: str) -> bool:
    """Basic URL validation — checks scheme prefix."""
    return value.startswith(("http://", "https://"))


def _validate_field(value: Any, schema: FieldSchema, path: str) -> list[str]:
    """Validate a single field value against its schema. Returns errors."""
    errors: list[str] = []

    if value is None:
        if schema.required and not schema.nullable:
            errors.append(f"{path}: required field is missing")
        return errors

    if schema.dtype == "str":
        if not isinstance(value, str):
            errors.append(f"{path}: expected string, got {type(value).__name__}")

    elif schema.dtype == "int":
        if not isinstance(value, int) or isinstance(value, bool):
            errors.append(f"{path}: expected integer, got {type(value).__name__}")
        elif schema.min_value is not None and value < schema.min_value:
            errors.append(f"{path}: value {value} below minimum {schema.min_value}")
        elif schema.max_value is not None and value > schema.max_value:
            errors.append(f"{path}: value {value} above maximum {schema.max_value}")

    elif schema.dtype == "float":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            errors.append(f"{path}: expected number, got {type(value).__name__}")
        elif schema.min_value is not None and value < schema.min_value:
            errors.append(f"{path}: value {value} below minimum {schema.min_value}")
        elif schema.max_value is not None and value > schema.max_value:
            errors.append(f"{path}: value {value} above maximum {schema.max_value}")

    elif schema.dtype == "bool":
        if not isinstance(value, bool):
            errors.append(f"{path}: expected boolean, got {type(value).__name__}")

    elif schema.dtype == "enum":
        if value not in schema.enum_values:
            errors.append(
                f"{path}: invalid value '{value}', expected one of {schema.enum_values}"
            )

    elif schema.dtype == "time":
        if not isinstance(value, str):
            errors.append(
                f"{path}: expected time string (HH:MM), got {type(value).__name__}"
            )
        elif not _validate_time(value):
            errors.append(f"{path}: invalid time format '{value}', expected HH:MM")

    elif schema.dtype == "timezone":
        if not isinstance(value, str):
            errors.append(
                f"{path}: expected timezone string, got {type(value).__name__}"
            )
        elif not _validate_timezone(value):
            errors.append(f"{path}: invalid timezone '{value}'")

    elif schema.dtype == "url":
        if not isinstance(value, str):
            errors.append(f"{path}: expected URL string, got {type(value).__name__}")
        elif not _validate_url(value):
            errors.append(
                f"{path}: invalid URL '{value}', must start with http:// or https://"
            )

    elif schema.dtype == "dict":
        if not isinstance(value, dict):
            errors.append(f"{path}: expected object, got {type(value).__name__}")
        else:
            errors.extend(_validate_object(value, schema.children, path))

    elif schema.dtype == "list":
        if not isinstance(value, list):
            errors.append(f"{path}: expected array, got {type(value).__name__}")
        elif schema.item_schema:
            for i, item in enumerate(value):
                if not isinstance(item, dict):
                    errors.append(
                        f"{path}[{i}]: expected object, got {type(item).__name__}"
                    )
                else:
                    errors.extend(
                        _validate_object(item, schema.item_schema, f"{path}[{i}]")
                    )

    return errors


def _validate_object(
    data: dict[str, Any], fields: list[FieldSchema], prefix: str
) -> list[str]:
    """Validate a dict against a list of field schemas."""
    errors: list[str] = []
    for fld in fields:
        path = f"{prefix}.{fld.name}"
        if fld.name not in data:
            if fld.required:
                errors.append(f"{path}: required field is missing")
            continue
        errors.extend(_validate_field(data[fld.name], fld, path))
    return errors


def validate_config(filepath: Path, schema: ConfigSchema) -> list[str]:
    """Validate a JSON config file against its schema. Returns list of errors."""
    errors: list[str] = []

    if not filepath.exists():
        errors.append(f"File not found: {filepath}")
        return errors

    try:
        with filepath.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON: {e}")
        return errors

    if not isinstance(data, dict):
        errors.append(f"Expected top-level object, got {type(data).__name__}")
        return errors

    errors.extend(_validate_object(data, schema.fields, schema.name))
    return errors


def validate_all_configs(config_dir: Path) -> dict[str, list[str]]:
    """Validate all config files. Returns dict of schema_name -> errors."""
    results: dict[str, list[str]] = {}
    for name, schema in SCHEMAS.items():
        filepath = config_dir / f"{name}.json"
        results[name] = validate_config(filepath, schema)
    return results
