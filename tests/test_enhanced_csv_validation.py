#!/usr/bin/env python3
"""Tests for enhanced CSV validation features."""

from __future__ import annotations

import tempfile
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "01-ops" / "life-os" / "scripts" / "validate_csv_integrity.py"
SPEC = spec_from_file_location("life_os_validate_csv_integrity", MODULE_PATH)
validate_csv_integrity = module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(validate_csv_integrity)


class TestNumericValidation:
    """Test numeric field validation functionality."""

    def test_validate_numeric_field_valid_integers(self) -> None:
        """Test numeric validation accepts valid integers."""
        valid, error = validate_csv_integrity.validate_numeric_field(
            "5", "priority", min_val=1, max_val=5, is_integer=True
        )
        assert valid
        assert error == ""

    def test_validate_numeric_field_invalid_integers(self) -> None:
        """Test numeric validation rejects invalid integers."""
        # Non-integer
        valid, error = validate_csv_integrity.validate_numeric_field(
            "abc", "priority", is_integer=True
        )
        assert not valid
        assert "not a valid integer" in error

        # Below minimum
        valid, error = validate_csv_integrity.validate_numeric_field(
            "0", "priority", min_val=1, is_integer=True
        )
        assert not valid
        assert "below minimum" in error

        # Above maximum
        valid, error = validate_csv_integrity.validate_numeric_field(
            "10", "priority", max_val=5, is_integer=True
        )
        assert not valid
        assert "exceeds maximum" in error

    def test_validate_numeric_field_valid_floats(self) -> None:
        """Test numeric validation accepts valid floats."""
        valid, error = validate_csv_integrity.validate_numeric_field(
            "3.14", "metric", min_val=0, is_integer=False
        )
        assert valid
        assert error == ""

    def test_validate_numeric_field_invalid_floats(self) -> None:
        """Test numeric validation rejects invalid floats."""
        valid, error = validate_csv_integrity.validate_numeric_field(
            "not_a_number", "metric", is_integer=False
        )
        assert not valid
        assert "not a valid number" in error

    def test_validate_numeric_field_empty_values(self) -> None:
        """Test numeric validation allows empty values."""
        valid, error = validate_csv_integrity.validate_numeric_field("", "priority")
        assert valid
        assert error == ""


class TestTimeRangeValidation:
    """Test time range validation functionality."""

    def test_validate_time_range_valid(self) -> None:
        """Test time range validation accepts valid ranges."""
        valid, error = validate_csv_integrity.validate_time_range("09:00", "10:00")
        assert valid
        assert error == ""

        valid, error = validate_csv_integrity.validate_time_range("23:30", "23:59")
        assert valid
        assert error == ""

    def test_validate_time_range_invalid(self) -> None:
        """Test time range validation rejects invalid ranges."""
        valid, error = validate_csv_integrity.validate_time_range("10:00", "09:00")
        assert not valid
        assert "must be before" in error

        valid, error = validate_csv_integrity.validate_time_range("12:00", "12:00")
        assert not valid
        assert "must be before" in error

    def test_validate_time_range_empty_values(self) -> None:
        """Test time range validation handles empty values."""
        valid, error = validate_csv_integrity.validate_time_range("", "10:00")
        assert valid
        assert error == ""

        valid, error = validate_csv_integrity.validate_time_range("09:00", "")
        assert valid
        assert error == ""


class TestDurationConsistency:
    """Test duration consistency validation."""

    def test_validate_duration_consistency_valid(self) -> None:
        """Test duration validation accepts consistent durations."""
        valid, error = validate_csv_integrity.validate_duration_consistency(
            "09:00", "10:00", "60"
        )
        assert valid
        assert error == ""

        valid, error = validate_csv_integrity.validate_duration_consistency(
            "14:30", "15:45", "75"
        )
        assert valid
        assert error == ""

    def test_validate_duration_consistency_invalid(self) -> None:
        """Test duration validation rejects inconsistent durations."""
        valid, error = validate_csv_integrity.validate_duration_consistency(
            "09:00", "10:00", "30"
        )
        assert not valid
        assert "doesn't match calculated duration" in error

    def test_validate_duration_consistency_midnight_rollover(self) -> None:
        """Test duration validation handles midnight rollover."""
        valid, error = validate_csv_integrity.validate_duration_consistency(
            "23:30", "00:30", "60"
        )
        assert valid
        assert error == ""

    def test_validate_duration_consistency_tolerance(self) -> None:
        """Test duration validation allows 1-minute tolerance."""
        valid, error = validate_csv_integrity.validate_duration_consistency(
            "09:00", "10:00", "59"
        )
        assert valid  # Should pass with 1-minute tolerance
        assert error == ""

        valid, error = validate_csv_integrity.validate_duration_consistency(
            "09:00", "10:00", "58"
        )
        assert not valid  # Should fail with 2-minute difference
        assert "doesn't match" in error


class TestDateRangeValidation:
    """Test date range validation functionality."""

    def test_validate_date_range_valid(self) -> None:
        """Test date range validation accepts valid ranges."""
        valid, error = validate_csv_integrity.validate_date_range(
            "2026-04-01", "2026-04-30", ("start_date", "end_date")
        )
        assert valid
        assert error == ""

        # Equal dates should be allowed
        valid, error = validate_csv_integrity.validate_date_range(
            "2026-04-01", "2026-04-01", ("start_date", "end_date")
        )
        assert valid
        assert error == ""

    def test_validate_date_range_invalid(self) -> None:
        """Test date range validation rejects invalid ranges."""
        valid, error = validate_csv_integrity.validate_date_range(
            "2026-04-30", "2026-04-01", ("start_date", "end_date")
        )
        assert not valid
        assert "must be before or equal to" in error
        assert "start_date" in error
        assert "end_date" in error

    def test_validate_date_range_empty_values(self) -> None:
        """Test date range validation handles empty values."""
        valid, error = validate_csv_integrity.validate_date_range(
            "", "2026-04-30", ("start_date", "end_date")
        )
        assert valid
        assert error == ""


class TestEnhancedSchemaValidation:
    """Test enhanced schema validation with new features."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_root = Path(self.temp_dir)

    def test_validate_csv_schema_numeric_validation(self) -> None:
        """Test schema validation catches numeric field violations."""
        tasks_file = self.test_root / "tasks.csv"
        content = (
            "task_id,project_id,title,domain,status,priority,effort_mins,due_date,energy,context,source,next_step,scheduled_date,scheduled_start,scheduled_end,last_updated,notes\n"
            "task1,,Test task,work,queued,P1,500,,medium,desk,manual,Do it,,,,2026-04-02,Test\n"  # effort_mins=500 > max=480
        )
        tasks_file.write_text(content, encoding="utf-8")

        result = validate_csv_integrity.validate_csv_schema(tasks_file)

        assert not result.passed
        assert any("exceeds maximum" in error for error in result.errors)

    def test_validate_csv_schema_time_range_validation(self) -> None:
        """Test schema validation catches time range violations."""
        time_blocks_file = self.test_root / "time_blocks.csv"
        content = (
            "block_id,date,start,end,title,domain,task_id,source,status,notes\n"
            "block1,2026-04-05,10:00,09:00,Work,work,,manual,planned,Invalid time range\n"
        )
        time_blocks_file.write_text(content, encoding="utf-8")

        result = validate_csv_integrity.validate_csv_schema(time_blocks_file)

        assert not result.passed
        assert any("must be before" in error for error in result.errors)

    def test_validate_csv_schema_duration_consistency_validation(self) -> None:
        """Test schema validation catches duration inconsistencies."""
        time_logs_file = self.test_root / "time_logs.csv"
        content = (
            "log_id,date,activity,domain,duration_mins,start_time,end_time,notes,last_updated\n"
            "log1,2026-04-05,Work,work,30,09:00,10:00,Wrong duration,\n"  # Should be 60 minutes
        )
        time_logs_file.write_text(content, encoding="utf-8")

        result = validate_csv_integrity.validate_csv_schema(time_logs_file)

        assert not result.passed
        assert any(
            "doesn't match calculated duration" in error for error in result.errors
        )

    def test_validate_csv_schema_date_range_validation(self) -> None:
        """Test schema validation catches date range violations."""
        projects_file = self.test_root / "projects.csv"
        content = (
            "project_id,area,name,status,start_date,target_date,description,last_updated,notes,active\n"
            "proj1,work,Test project,active,2026-04-30,2026-04-01,Test,2026-04-02,Invalid dates,true\n"
        )
        projects_file.write_text(content, encoding="utf-8")

        result = validate_csv_integrity.validate_csv_schema(projects_file)

        assert not result.passed
        assert any("must be before or equal to" in error for error in result.errors)

    def test_validate_csv_schema_habits_numeric_validation(self) -> None:
        """Test schema validation for habits CSV numeric fields."""
        habits_file = self.test_root / "habits.csv"
        content = (
            "habit_id,area,name,frequency,target_per_week,min_value,unit,active,notes,last_updated\n"
            "habit1,health,Test habit,daily,10,1,session,true,Test,2026-04-02\n"  # target_per_week=10 > max=7
        )
        habits_file.write_text(content, encoding="utf-8")

        result = validate_csv_integrity.validate_csv_schema(habits_file)

        assert not result.passed
        assert any("exceeds maximum" in error for error in result.errors)

    def test_validate_csv_schema_goals_numeric_validation(self) -> None:
        """Test schema validation for goals CSV numeric fields."""
        goals_file = self.test_root / "goals.csv"
        content = (
            "goal_id,area,title,horizon,target_date,metric_name,metric_target,metric_current,status,last_updated,notes\n"
            "goal1,health,Test goal,quarter,2026-06-01,sessions,-5,0,active,2026-04-02,Test\n"  # metric_target=-5 < min=0
        )
        goals_file.write_text(content, encoding="utf-8")

        result = validate_csv_integrity.validate_csv_schema(goals_file)

        assert not result.passed
        assert any("below minimum" in error for error in result.errors)

    def test_validate_csv_schema_passes_valid_data(self) -> None:
        """Test schema validation passes with valid enhanced data."""
        tasks_file = self.test_root / "tasks.csv"
        content = (
            "task_id,project_id,title,domain,status,priority,effort_mins,due_date,energy,context,source,next_step,scheduled_date,scheduled_start,scheduled_end,last_updated,notes\n"
            "task1,,Test task,work,queued,P3,60,2026-04-10,medium,desk,manual,Do it,2026-04-05,09:00,10:00,2026-04-02,Test\n"
        )
        tasks_file.write_text(content, encoding="utf-8")

        result = validate_csv_integrity.validate_csv_schema(tasks_file)

        assert result.passed
        assert len(result.errors) == 0
