"""Tests for configuration file validation."""

from __future__ import annotations

import copy
import json
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "01-ops" / "life-os" / "scripts" / "validate_config.py"
SPEC = spec_from_file_location("validate_config", MODULE_PATH)
validate_config = module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules["validate_config"] = validate_config
SPEC.loader.exec_module(validate_config)

validate_profile = validate_config.validate_profile
validate_calendar_feeds = validate_config.validate_calendar_feeds
validate_config_file = validate_config.validate_config_file
validate_all_configs = validate_config.validate_all_configs

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_PROFILE: dict = {
    "owner": "Test User",
    "timezone": "America/New_York",
    "planning": {
        "weekday_wake": "07:00",
        "weekend_earliest": "09:00",
        "day_end": "23:00",
        "bedtime": "23:00",
        "workday_commute_start": "08:30",
        "workday_start": "09:00",
        "workday_end": "17:00",
        "workday_commute_home_end": "17:30",
        "default_task_block_mins": 60,
        "deep_work_block_mins": 90,
        "max_screen_block_mins": 90,
        "break_mins": 15,
        "max_major_tasks_per_day": 4,
        "weekly_review_day": "Sunday",
    },
    "domains": [
        {"id": "career", "name": "Career", "weight": 10},
        {"id": "health", "name": "Health", "weight": 9},
    ],
    "energy_curve": [
        {"time": "07:00", "energy": "low"},
        {"time": "09:00", "energy": "high"},
    ],
    "priority_tiers": [
        {"tier": 1, "label": "Non-negotiable", "examples": "sleep, health"},
    ],
}

VALID_CALENDAR_FEEDS: dict = {
    "feeds": [
        {
            "name": "personal",
            "enabled": True,
            "url": "https://example.com/cal.ics",
            "output_file": "personal.ics",
            "timeout_seconds": 30,
        },
    ],
}


def _profile(**overrides: object) -> dict:
    """Return a copy of VALID_PROFILE with top-level overrides applied."""
    p = copy.deepcopy(VALID_PROFILE)
    p.update(overrides)
    return p


# ---------------------------------------------------------------------------
# Profile — happy path
# ---------------------------------------------------------------------------


class TestProfileValid:
    def test_valid_profile_passes(self) -> None:
        assert validate_profile(VALID_PROFILE) == []

    def test_comment_field_ignored(self) -> None:
        data = _profile(_comment="this is fine")
        assert validate_profile(data) == []


# ---------------------------------------------------------------------------
# Profile — top-level fields
# ---------------------------------------------------------------------------


class TestProfileTopLevel:
    def test_missing_owner(self) -> None:
        data = _profile()
        del data["owner"]
        errors = validate_profile(data)
        assert any("owner" in e for e in errors)

    def test_owner_wrong_type(self) -> None:
        errors = validate_profile(_profile(owner=123))
        assert any("owner" in e and "str" in e for e in errors)

    def test_missing_timezone(self) -> None:
        data = _profile()
        del data["timezone"]
        errors = validate_profile(data)
        assert any("timezone" in e for e in errors)

    def test_missing_planning(self) -> None:
        data = _profile()
        del data["planning"]
        errors = validate_profile(data)
        assert any("planning" in e for e in errors)

    def test_planning_wrong_type(self) -> None:
        errors = validate_profile(_profile(planning="oops"))
        assert any("planning" in e and "dict" in e for e in errors)


# ---------------------------------------------------------------------------
# Profile — planning section
# ---------------------------------------------------------------------------


class TestProfilePlanning:
    def test_missing_time_field(self) -> None:
        data = _profile()
        del data["planning"]["weekday_wake"]
        errors = validate_profile(data)
        assert any("weekday_wake" in e for e in errors)

    def test_invalid_time_format(self) -> None:
        data = _profile()
        data["planning"]["bedtime"] = "25:99"
        errors = validate_profile(data)
        assert any("bedtime" in e and "HH:MM" in e for e in errors)

    def test_time_field_wrong_type(self) -> None:
        data = _profile()
        data["planning"]["day_end"] = 2300
        errors = validate_profile(data)
        assert any("day_end" in e for e in errors)

    def test_missing_int_field(self) -> None:
        data = _profile()
        del data["planning"]["break_mins"]
        errors = validate_profile(data)
        assert any("break_mins" in e for e in errors)

    def test_int_field_negative(self) -> None:
        data = _profile()
        data["planning"]["break_mins"] = -5
        errors = validate_profile(data)
        assert any("break_mins" in e and "positive" in e for e in errors)

    def test_int_field_zero(self) -> None:
        data = _profile()
        data["planning"]["max_major_tasks_per_day"] = 0
        errors = validate_profile(data)
        assert any("max_major_tasks_per_day" in e for e in errors)

    def test_int_field_wrong_type(self) -> None:
        data = _profile()
        data["planning"]["deep_work_block_mins"] = "ninety"
        errors = validate_profile(data)
        assert any("deep_work_block_mins" in e for e in errors)

    def test_invalid_weekly_review_day(self) -> None:
        data = _profile()
        data["planning"]["weekly_review_day"] = "Funday"
        errors = validate_profile(data)
        assert any("weekly_review_day" in e for e in errors)


# ---------------------------------------------------------------------------
# Profile — domains
# ---------------------------------------------------------------------------


class TestProfileDomains:
    def test_missing_domains(self) -> None:
        data = _profile()
        del data["domains"]
        errors = validate_profile(data)
        assert any("domains" in e for e in errors)

    def test_domain_missing_id(self) -> None:
        data = _profile(domains=[{"name": "Career", "weight": 10}])
        errors = validate_profile(data)
        assert any("id" in e for e in errors)

    def test_domain_missing_name(self) -> None:
        data = _profile(domains=[{"id": "career", "weight": 10}])
        errors = validate_profile(data)
        assert any("name" in e for e in errors)

    def test_domain_negative_weight(self) -> None:
        data = _profile(domains=[{"id": "x", "name": "X", "weight": -1}])
        errors = validate_profile(data)
        assert any("weight" in e for e in errors)

    def test_domain_not_a_dict(self) -> None:
        data = _profile(domains=["career"])
        errors = validate_profile(data)
        assert any("expected object" in e for e in errors)


# ---------------------------------------------------------------------------
# Profile — energy curve
# ---------------------------------------------------------------------------


class TestProfileEnergyCurve:
    def test_missing_energy_curve(self) -> None:
        data = _profile()
        del data["energy_curve"]
        errors = validate_profile(data)
        assert any("energy_curve" in e for e in errors)

    def test_invalid_energy_level(self) -> None:
        data = _profile(energy_curve=[{"time": "09:00", "energy": "extreme"}])
        errors = validate_profile(data)
        assert any("energy" in e and "extreme" in e for e in errors)

    def test_invalid_time_in_curve(self) -> None:
        data = _profile(energy_curve=[{"time": "nope", "energy": "high"}])
        errors = validate_profile(data)
        assert any("time" in e and "HH:MM" in e for e in errors)

    def test_missing_energy_field(self) -> None:
        data = _profile(energy_curve=[{"time": "09:00"}])
        errors = validate_profile(data)
        assert any("energy" in e and "missing" in e for e in errors)

    def test_missing_time_field(self) -> None:
        data = _profile(energy_curve=[{"energy": "high"}])
        errors = validate_profile(data)
        assert any("time" in e and "missing" in e for e in errors)

    def test_entry_not_a_dict(self) -> None:
        data = _profile(energy_curve=["09:00"])
        errors = validate_profile(data)
        assert any("expected object" in e for e in errors)


# ---------------------------------------------------------------------------
# Profile — priority tiers
# ---------------------------------------------------------------------------


class TestProfilePriorityTiers:
    def test_tiers_optional(self) -> None:
        data = _profile()
        del data["priority_tiers"]
        assert validate_profile(data) == []

    def test_tier_invalid_number(self) -> None:
        data = _profile(priority_tiers=[{"tier": 0, "label": "Bad"}])
        errors = validate_profile(data)
        assert any("tier" in e and "positive" in e for e in errors)

    def test_tier_missing_label(self) -> None:
        data = _profile(priority_tiers=[{"tier": 1}])
        errors = validate_profile(data)
        assert any("label" in e for e in errors)

    def test_tiers_wrong_type(self) -> None:
        errors = validate_profile(_profile(priority_tiers="bad"))
        assert any("priority_tiers" in e and "list" in e for e in errors)

    def test_tier_entry_not_dict(self) -> None:
        errors = validate_profile(_profile(priority_tiers=[42]))
        assert any("expected object" in e for e in errors)


# ---------------------------------------------------------------------------
# Calendar feeds
# ---------------------------------------------------------------------------


class TestCalendarFeeds:
    def test_valid_feeds_passes(self) -> None:
        assert validate_calendar_feeds(VALID_CALENDAR_FEEDS) == []

    def test_missing_feeds_key(self) -> None:
        errors = validate_calendar_feeds({})
        assert any("feeds" in e for e in errors)

    def test_feeds_wrong_type(self) -> None:
        errors = validate_calendar_feeds({"feeds": "bad"})
        assert any("feeds" in e and "list" in e for e in errors)

    def test_feed_missing_name(self) -> None:
        feed = {"url": "https://x", "output_file": "x.ics"}
        errors = validate_calendar_feeds({"feeds": [feed]})
        assert any("name" in e for e in errors)

    def test_feed_missing_url(self) -> None:
        feed = {"name": "x", "output_file": "x.ics"}
        errors = validate_calendar_feeds({"feeds": [feed]})
        assert any("url" in e for e in errors)

    def test_feed_enabled_wrong_type(self) -> None:
        feed = {
            "name": "x",
            "url": "https://x",
            "output_file": "x.ics",
            "enabled": "yes",
        }
        errors = validate_calendar_feeds({"feeds": [feed]})
        assert any("enabled" in e and "boolean" in e for e in errors)

    def test_feed_timeout_negative(self) -> None:
        feed = {
            "name": "x",
            "url": "https://x",
            "output_file": "x.ics",
            "timeout_seconds": -1,
        }
        errors = validate_calendar_feeds({"feeds": [feed]})
        assert any("timeout_seconds" in e for e in errors)

    def test_feed_not_a_dict(self) -> None:
        errors = validate_calendar_feeds({"feeds": ["bad"]})
        assert any("expected object" in e for e in errors)


# ---------------------------------------------------------------------------
# File-level validation
# ---------------------------------------------------------------------------


class TestValidateConfigFile:
    def test_file_not_found(self, tmp_path: Path) -> None:
        errors = validate_config_file(tmp_path / "missing.json")
        assert any("File not found" in e for e in errors)

    def test_invalid_json(self, tmp_path: Path) -> None:
        p = tmp_path / "profile.json"
        p.write_text("{bad json", encoding="utf-8")
        errors = validate_config_file(p)
        assert any("Invalid JSON" in e for e in errors)

    def test_top_level_not_object(self, tmp_path: Path) -> None:
        p = tmp_path / "profile.json"
        p.write_text("[]", encoding="utf-8")
        errors = validate_config_file(p)
        assert any("JSON object" in e for e in errors)

    def test_valid_profile_file(self, tmp_path: Path) -> None:
        p = tmp_path / "profile.json"
        p.write_text(json.dumps(VALID_PROFILE), encoding="utf-8")
        assert validate_config_file(p) == []

    def test_valid_calendar_feeds_file(self, tmp_path: Path) -> None:
        p = tmp_path / "calendar_feeds.json"
        p.write_text(json.dumps(VALID_CALENDAR_FEEDS), encoding="utf-8")
        assert validate_config_file(p) == []

    def test_unknown_config_file(self, tmp_path: Path) -> None:
        p = tmp_path / "mystery.json"
        p.write_text("{}", encoding="utf-8")
        errors = validate_config_file(p)
        assert any("No validation schema" in e for e in errors)

    def test_example_profile_validates(self) -> None:
        """The shipped example config must pass validation."""
        example = (
            REPO_ROOT / "01-ops" / "life-os" / "config" / "profile.example.json"
        )
        if example.exists():
            assert validate_config_file(example) == []


# ---------------------------------------------------------------------------
# Validate all configs
# ---------------------------------------------------------------------------


class TestValidateAllConfigs:
    def test_validates_directory(self, tmp_path: Path) -> None:
        p = tmp_path / "profile.json"
        p.write_text(json.dumps(VALID_PROFILE), encoding="utf-8")
        c = tmp_path / "calendar_feeds.json"
        c.write_text(json.dumps(VALID_CALENDAR_FEEDS), encoding="utf-8")
        results = validate_all_configs(tmp_path)
        assert results["profile.json"] == []
        assert results["calendar_feeds.json"] == []

    def test_empty_directory(self, tmp_path: Path) -> None:
        assert validate_all_configs(tmp_path) == {}
