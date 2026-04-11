"""Tests for configuration file schema definitions and validation."""

from __future__ import annotations

import json
import sys
import tempfile
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "01-ops" / "life-os" / "scripts" / "config_schemas.py"
SPEC = spec_from_file_location("config_schemas", MODULE_PATH)
config_schemas = module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["config_schemas"] = config_schemas
SPEC.loader.exec_module(config_schemas)

FieldSchema = config_schemas.FieldSchema
ConfigSchema = config_schemas.ConfigSchema
SCHEMAS = config_schemas.SCHEMAS
PROFILE_SCHEMA = config_schemas.PROFILE_SCHEMA
CALENDAR_FEEDS_SCHEMA = config_schemas.CALENDAR_FEEDS_SCHEMA
validate_config = config_schemas.validate_config
validate_all_configs = config_schemas.validate_all_configs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_json(data: dict, tmp_dir: Path, name: str = "test.json") -> Path:
    filepath = tmp_dir / name
    filepath.write_text(json.dumps(data), encoding="utf-8")
    return filepath


def _valid_profile() -> dict:
    """Return a minimal valid profile config."""
    return {
        "owner": "Test User",
        "timezone": "America/New_York",
        "planning": {
            "weekday_wake": "07:00",
            "weekend_earliest": "09:00",
            "day_end": "23:00",
            "bedtime": "23:00",
        },
        "domains": [
            {"id": "career", "name": "Career", "weight": 10},
        ],
        "energy_curve": [
            {"time": "09:00", "energy": "high"},
        ],
        "priority_tiers": [
            {"tier": 1, "label": "Non-negotiable", "examples": "sleep"},
        ],
    }


def _valid_calendar_feeds() -> dict:
    return {
        "feeds": [
            {
                "name": "personal",
                "enabled": True,
                "url": "https://calendar.google.com/cal.ics",
                "output_file": "personal.ics",
                "timeout_seconds": 30,
            },
        ],
    }


# ---------------------------------------------------------------------------
# Schema definition tests
# ---------------------------------------------------------------------------


def test_all_config_schemas_defined() -> None:
    assert set(SCHEMAS.keys()) == {"profile", "calendar_feeds"}


def test_profile_schema_has_required_fields() -> None:
    names = [f.name for f in PROFILE_SCHEMA.fields]
    assert "owner" in names
    assert "timezone" in names
    assert "planning" in names
    assert "domains" in names
    assert "energy_curve" in names
    assert "priority_tiers" in names


def test_calendar_feeds_schema_has_feeds_field() -> None:
    names = [f.name for f in CALENDAR_FEEDS_SCHEMA.fields]
    assert "feeds" in names


# ---------------------------------------------------------------------------
# Valid config tests
# ---------------------------------------------------------------------------


def test_valid_profile_passes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_json(_valid_profile(), Path(tmp))
        errors = validate_config(path, PROFILE_SCHEMA)
        assert errors == []


def test_valid_calendar_feeds_passes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_json(_valid_calendar_feeds(), Path(tmp))
        errors = validate_config(path, CALENDAR_FEEDS_SCHEMA)
        assert errors == []


def test_example_profile_validates() -> None:
    """The shipped profile.example.json should pass validation."""
    example = REPO_ROOT / "01-ops" / "life-os" / "config" / "profile.example.json"
    errors = validate_config(example, PROFILE_SCHEMA)
    assert errors == []


def test_example_calendar_feeds_validates() -> None:
    """The shipped calendar_feeds.example.json should pass validation."""
    example = (
        REPO_ROOT / "01-ops" / "life-os" / "config" / "calendar_feeds.example.json"
    )
    errors = validate_config(example, CALENDAR_FEEDS_SCHEMA)
    assert errors == []


# ---------------------------------------------------------------------------
# File-level error tests
# ---------------------------------------------------------------------------


def test_missing_file() -> None:
    errors = validate_config(Path("/nonexistent/file.json"), PROFILE_SCHEMA)
    assert len(errors) == 1
    assert "File not found" in errors[0]


def test_invalid_json() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "bad.json"
        path.write_text("{not valid json", encoding="utf-8")
        errors = validate_config(path, PROFILE_SCHEMA)
        assert len(errors) == 1
        assert "Invalid JSON" in errors[0]


def test_non_object_top_level() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "list.json"
        path.write_text("[]", encoding="utf-8")
        errors = validate_config(path, PROFILE_SCHEMA)
        assert len(errors) == 1
        assert "Expected top-level object" in errors[0]


# ---------------------------------------------------------------------------
# Required field tests
# ---------------------------------------------------------------------------


def test_missing_required_field() -> None:
    data = _valid_profile()
    del data["owner"]
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_json(data, Path(tmp))
        errors = validate_config(path, PROFILE_SCHEMA)
        assert any("owner" in e and "required" in e for e in errors)


def test_missing_nested_required_field() -> None:
    data = _valid_profile()
    del data["planning"]["weekday_wake"]
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_json(data, Path(tmp))
        errors = validate_config(path, PROFILE_SCHEMA)
        assert any("weekday_wake" in e for e in errors)


def test_missing_required_in_list_item() -> None:
    data = _valid_profile()
    data["domains"] = [{"id": "career"}]  # missing name and weight
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_json(data, Path(tmp))
        errors = validate_config(path, PROFILE_SCHEMA)
        assert any("name" in e and "required" in e for e in errors)
        assert any("weight" in e and "required" in e for e in errors)


# ---------------------------------------------------------------------------
# Type validation tests
# ---------------------------------------------------------------------------


def test_invalid_timezone() -> None:
    data = _valid_profile()
    data["timezone"] = "Not/A_Real_Timezone"
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_json(data, Path(tmp))
        errors = validate_config(path, PROFILE_SCHEMA)
        assert any("invalid timezone" in e for e in errors)


def test_invalid_time_format() -> None:
    data = _valid_profile()
    data["planning"]["weekday_wake"] = "7:00"  # missing leading zero
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_json(data, Path(tmp))
        errors = validate_config(path, PROFILE_SCHEMA)
        assert any("invalid time" in e for e in errors)


def test_invalid_time_out_of_range() -> None:
    data = _valid_profile()
    data["planning"]["weekday_wake"] = "25:00"
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_json(data, Path(tmp))
        errors = validate_config(path, PROFILE_SCHEMA)
        assert any("invalid time" in e for e in errors)


def test_invalid_enum_value() -> None:
    data = _valid_profile()
    data["energy_curve"] = [{"time": "09:00", "energy": "extreme"}]
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_json(data, Path(tmp))
        errors = validate_config(path, PROFILE_SCHEMA)
        assert any("invalid value" in e and "extreme" in e for e in errors)


def test_int_below_minimum() -> None:
    data = _valid_profile()
    data["planning"]["default_task_block_mins"] = 0
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_json(data, Path(tmp))
        errors = validate_config(path, PROFILE_SCHEMA)
        assert any("below minimum" in e for e in errors)


def test_int_above_maximum() -> None:
    data = _valid_profile()
    data["planning"]["default_task_block_mins"] = 999
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_json(data, Path(tmp))
        errors = validate_config(path, PROFILE_SCHEMA)
        assert any("above maximum" in e for e in errors)


def test_wrong_type_string_instead_of_int() -> None:
    data = _valid_profile()
    data["domains"] = [{"id": "career", "name": "Career", "weight": "ten"}]
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_json(data, Path(tmp))
        errors = validate_config(path, PROFILE_SCHEMA)
        assert any("expected integer" in e for e in errors)


def test_wrong_type_dict_field() -> None:
    data = _valid_profile()
    data["planning"] = "not a dict"
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_json(data, Path(tmp))
        errors = validate_config(path, PROFILE_SCHEMA)
        assert any("expected object" in e for e in errors)


def test_wrong_type_list_field() -> None:
    data = _valid_profile()
    data["domains"] = "not a list"
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_json(data, Path(tmp))
        errors = validate_config(path, PROFILE_SCHEMA)
        assert any("expected array" in e for e in errors)


# ---------------------------------------------------------------------------
# URL validation tests
# ---------------------------------------------------------------------------


def test_valid_url_passes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_json(_valid_calendar_feeds(), Path(tmp))
        errors = validate_config(path, CALENDAR_FEEDS_SCHEMA)
        assert errors == []


def test_invalid_url_fails() -> None:
    data = _valid_calendar_feeds()
    data["feeds"][0]["url"] = "ftp://not-http.com/cal"
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_json(data, Path(tmp))
        errors = validate_config(path, CALENDAR_FEEDS_SCHEMA)
        assert any("invalid URL" in e for e in errors)


# ---------------------------------------------------------------------------
# Bool validation tests
# ---------------------------------------------------------------------------


def test_bool_wrong_type() -> None:
    data = _valid_calendar_feeds()
    data["feeds"][0]["enabled"] = "yes"
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_json(data, Path(tmp))
        errors = validate_config(path, CALENDAR_FEEDS_SCHEMA)
        assert any("expected boolean" in e for e in errors)


# ---------------------------------------------------------------------------
# List item validation tests
# ---------------------------------------------------------------------------


def test_list_item_not_object() -> None:
    data = _valid_profile()
    data["domains"] = ["career", "health"]
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_json(data, Path(tmp))
        errors = validate_config(path, PROFILE_SCHEMA)
        assert any("expected object" in e for e in errors)


# ---------------------------------------------------------------------------
# validate_all_configs tests
# ---------------------------------------------------------------------------


def test_validate_all_configs_returns_all_schemas() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _write_json(_valid_profile(), tmp_path, "profile.json")
        _write_json(_valid_calendar_feeds(), tmp_path, "calendar_feeds.json")
        results = validate_all_configs(tmp_path)
        assert set(results.keys()) == {"profile", "calendar_feeds"}
        assert results["profile"] == []
        assert results["calendar_feeds"] == []


def test_validate_all_configs_missing_files() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        results = validate_all_configs(Path(tmp))
        assert all("File not found" in errs[0] for errs in results.values())


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_extra_fields_are_ignored() -> None:
    """Unknown fields in the config should not cause errors."""
    data = _valid_profile()
    data["_comment"] = "This is a comment"
    data["custom_field"] = 42
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_json(data, Path(tmp))
        errors = validate_config(path, PROFILE_SCHEMA)
        assert errors == []


def test_empty_list_passes() -> None:
    """An empty list for a required list field should pass."""
    data = _valid_profile()
    data["domains"] = []
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_json(data, Path(tmp))
        errors = validate_config(path, PROFILE_SCHEMA)
        assert errors == []


def test_bool_not_treated_as_int() -> None:
    """Python bools are ints, but we should reject True for an int field."""
    data = _valid_profile()
    data["planning"]["default_task_block_mins"] = True
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_json(data, Path(tmp))
        errors = validate_config(path, PROFILE_SCHEMA)
        assert any("expected integer" in e for e in errors)


# ---------------------------------------------------------------------------
# Nullable field tests (covers lines 169-171)
# ---------------------------------------------------------------------------


def test_nullable_field_accepts_none() -> None:
    """A nullable field should accept None without error."""
    schema = ConfigSchema(
        name="test",
        fields=[FieldSchema("opt", required=True, nullable=True, dtype="str")],
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_json({"opt": None}, Path(tmp))
        errors = validate_config(path, schema)
        assert errors == []


def test_required_non_nullable_rejects_none() -> None:
    """A required, non-nullable field should reject None."""
    schema = ConfigSchema(
        name="test",
        fields=[FieldSchema("val", required=True, nullable=False, dtype="str")],
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_json({"val": None}, Path(tmp))
        errors = validate_config(path, schema)
        assert any("required field is missing" in e for e in errors)


# ---------------------------------------------------------------------------
# String type wrong-type check (covers line 175)
# ---------------------------------------------------------------------------


def test_string_field_rejects_non_string() -> None:
    """A str-typed field should reject a non-string value."""
    schema = ConfigSchema(
        name="test",
        fields=[FieldSchema("name", required=True, dtype="str")],
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_json({"name": 42}, Path(tmp))
        errors = validate_config(path, schema)
        assert any("expected string" in e for e in errors)


# ---------------------------------------------------------------------------
# Float validation (covers lines 186-191)
# ---------------------------------------------------------------------------


def test_float_field_rejects_non_number() -> None:
    """A float-typed field should reject a string value."""
    schema = ConfigSchema(
        name="test",
        fields=[FieldSchema("score", required=True, dtype="float")],
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_json({"score": "abc"}, Path(tmp))
        errors = validate_config(path, schema)
        assert any("expected number" in e for e in errors)


def test_float_field_rejects_bool() -> None:
    """A float-typed field should reject a boolean."""
    schema = ConfigSchema(
        name="test",
        fields=[FieldSchema("score", required=True, dtype="float")],
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_json({"score": True}, Path(tmp))
        errors = validate_config(path, schema)
        assert any("expected number" in e for e in errors)


def test_float_below_minimum() -> None:
    schema = ConfigSchema(
        name="test",
        fields=[FieldSchema("val", required=True, dtype="float", min_value=1.0)],
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_json({"val": 0.5}, Path(tmp))
        errors = validate_config(path, schema)
        assert any("below minimum" in e for e in errors)


def test_float_above_maximum() -> None:
    schema = ConfigSchema(
        name="test",
        fields=[FieldSchema("val", required=True, dtype="float", max_value=10.0)],
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_json({"val": 15.0}, Path(tmp))
        errors = validate_config(path, schema)
        assert any("above maximum" in e for e in errors)


# ---------------------------------------------------------------------------
# Non-string type for time/timezone/url (covers lines 205, 211, 217)
# ---------------------------------------------------------------------------


def test_time_field_rejects_non_string() -> None:
    schema = ConfigSchema(
        name="test",
        fields=[FieldSchema("t", required=True, dtype="time")],
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_json({"t": 900}, Path(tmp))
        errors = validate_config(path, schema)
        assert any("expected time string" in e for e in errors)


def test_timezone_field_rejects_non_string() -> None:
    schema = ConfigSchema(
        name="test",
        fields=[FieldSchema("tz", required=True, dtype="timezone")],
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_json({"tz": 123}, Path(tmp))
        errors = validate_config(path, schema)
        assert any("expected timezone string" in e for e in errors)


def test_url_field_rejects_non_string() -> None:
    schema = ConfigSchema(
        name="test",
        fields=[FieldSchema("link", required=True, dtype="url")],
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_json({"link": 42}, Path(tmp))
        errors = validate_config(path, schema)
        assert any("expected URL string" in e for e in errors)


# ---------------------------------------------------------------------------
# Dict type recursive validation (covers line 224-225)
# ---------------------------------------------------------------------------


def test_dict_field_validates_children() -> None:
    """A valid dict with children should pass recursive validation."""
    schema = ConfigSchema(
        name="test",
        fields=[
            FieldSchema(
                "settings",
                required=True,
                dtype="dict",
                children=[FieldSchema("key", required=True, dtype="str")],
            ),
        ],
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_json({"settings": {"key": "value"}}, Path(tmp))
        errors = validate_config(path, schema)
        assert errors == []


def test_dict_field_reports_child_errors() -> None:
    """A dict with missing required children should report errors."""
    schema = ConfigSchema(
        name="test",
        fields=[
            FieldSchema(
                "settings",
                required=True,
                dtype="dict",
                children=[FieldSchema("key", required=True, dtype="str")],
            ),
        ],
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_json({"settings": {}}, Path(tmp))
        errors = validate_config(path, schema)
        assert any("key" in e and "required" in e for e in errors)
