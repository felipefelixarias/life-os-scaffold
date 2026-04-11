#!/usr/bin/env python3
"""Comprehensive tests for CSV data validation functionality."""

from __future__ import annotations

import tempfile
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest import mock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "01-ops" / "life-os" / "scripts" / "validate_csv_integrity.py"
SPEC = spec_from_file_location("life_os_validate_csv_integrity", MODULE_PATH)
validate_csv_integrity = module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(validate_csv_integrity)


class TestValidationResult:
    """Test the ValidationResult class."""

    def test_initialization(self) -> None:
        """Test ValidationResult initializes correctly."""
        file_path = Path("test.csv")
        result = validate_csv_integrity.ValidationResult(file_path)

        assert result.file_path == file_path
        assert result.errors == []
        assert result.warnings == []
        assert result.passed is True

    def test_add_error(self) -> None:
        """Test adding errors marks result as failed."""
        result = validate_csv_integrity.ValidationResult(Path("test.csv"))
        result.add_error("Test error")

        assert len(result.errors) == 1
        assert result.errors[0] == "Test error"
        assert result.passed is False

    def test_add_warning(self) -> None:
        """Test adding warnings doesn't affect pass status."""
        result = validate_csv_integrity.ValidationResult(Path("test.csv"))
        result.add_warning("Test warning")

        assert len(result.warnings) == 1
        assert result.warnings[0] == "Test warning"
        assert result.passed is True

    def test_multiple_errors_and_warnings(self) -> None:
        """Test multiple errors and warnings are tracked correctly."""
        result = validate_csv_integrity.ValidationResult(Path("test.csv"))
        result.add_error("Error 1")
        result.add_error("Error 2")
        result.add_warning("Warning 1")

        assert len(result.errors) == 2
        assert len(result.warnings) == 1
        assert result.passed is False


class TestDateTimeValidation:
    """Test date and time validation functions."""

    @pytest.mark.parametrize("date_str", ["2026-04-05", "2025-01-01", "2026-12-31"])
    def test_validate_date_format_valid_dates(self, date_str: str) -> None:
        """Test date validation accepts valid YYYY-MM-DD dates."""
        assert validate_csv_integrity.validate_date_format(date_str)

    @pytest.mark.parametrize(
        "date_str", ["04-05-2026", "2026/04/05", "invalid", "2026-13-01"]
    )
    def test_validate_date_format_invalid_dates(self, date_str: str) -> None:
        """Test date validation rejects invalid dates."""
        assert not validate_csv_integrity.validate_date_format(date_str)

    def test_validate_date_format_empty_string(self) -> None:
        """Test empty dates are considered valid (optional)."""
        assert validate_csv_integrity.validate_date_format("")
        assert validate_csv_integrity.validate_date_format("   ")

    @pytest.mark.parametrize("time_str", ["09:30", "23:59", "00:00", "12:00"])
    def test_validate_time_format_valid_times(self, time_str: str) -> None:
        """Test time validation accepts valid HH:MM times."""
        assert validate_csv_integrity.validate_time_format(time_str)

    @pytest.mark.parametrize("time_str", ["24:00", "12:60", "invalid", "12:30:45"])
    def test_validate_time_format_invalid_times(self, time_str: str) -> None:
        """Test time validation rejects invalid times."""
        assert not validate_csv_integrity.validate_time_format(time_str)

    def test_validate_time_format_empty_string(self) -> None:
        """Test empty times are considered valid (optional)."""
        assert validate_csv_integrity.validate_time_format("")
        assert validate_csv_integrity.validate_time_format("   ")


class TestCsvSchemaValidation:
    """Test CSV schema validation functionality."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_root = Path(self.temp_dir)

    def test_validate_csv_schema_missing_file(self) -> None:
        """Test validation handles missing files gracefully."""
        missing_file = self.test_root / "missing.csv"
        result = validate_csv_integrity.validate_csv_schema(missing_file)

        assert not result.passed
        assert len(result.errors) == 1
        assert "does not exist" in result.errors[0]

    def test_validate_csv_schema_unknown_file(self) -> None:
        """Test validation warns about unknown file schemas."""
        unknown_file = self.test_root / "unknown.csv"
        unknown_file.write_text("col1,col2\nval1,val2\n", encoding="utf-8")

        result = validate_csv_integrity.validate_csv_schema(unknown_file)

        assert result.passed
        assert len(result.warnings) == 1
        assert "No schema definition found" in result.warnings[0]

    def test_validate_csv_schema_empty_file(self) -> None:
        """Test validation handles empty files."""
        empty_file = self.test_root / "habits.csv"
        empty_file.write_text("", encoding="utf-8")

        result = validate_csv_integrity.validate_csv_schema(empty_file)

        assert not result.passed
        assert "empty or has no headers" in result.errors[0]

    def test_validate_csv_schema_correct_habits_file(self) -> None:
        """Test validation passes for correct habits.csv."""
        habits_file = self.test_root / "habits.csv"
        content = (
            "habit_id,area,name,frequency,target_per_week,min_value,unit,active,notes,last_updated\n"
            "sleep_7h,health,Sleep 7+ hours,daily,7,7,hours,true,Good sleep,2026-04-02\n"
        )
        habits_file.write_text(content, encoding="utf-8")

        result = validate_csv_integrity.validate_csv_schema(habits_file)

        assert result.passed
        assert len(result.errors) == 0

    def test_validate_csv_schema_header_mismatch(self) -> None:
        """Test validation catches schema mismatches."""
        habits_file = self.test_root / "habits.csv"
        content = "wrong,headers\nval1,val2\n"
        habits_file.write_text(content, encoding="utf-8")

        result = validate_csv_integrity.validate_csv_schema(habits_file)

        assert not result.passed
        assert "Schema mismatch" in result.errors[0]

    def test_validate_csv_schema_column_count_mismatch(self) -> None:
        """Test validation catches column count mismatches."""
        habits_file = self.test_root / "habits.csv"
        content = (
            "habit_id,area,name,frequency,target_per_week,min_value,unit,active,notes,last_updated\n"
            "sleep_7h,health,Sleep 7+ hours,daily,7\n"  # Missing columns
        )
        habits_file.write_text(content, encoding="utf-8")

        result = validate_csv_integrity.validate_csv_schema(habits_file)

        assert not result.passed
        assert "has 5 columns, expected 10" in result.errors[0]

    def test_validate_csv_schema_duplicate_ids(self) -> None:
        """Test validation catches duplicate IDs."""
        habits_file = self.test_root / "habits.csv"
        content = (
            "habit_id,area,name,frequency,target_per_week,min_value,unit,active,notes,last_updated\n"
            "sleep_7h,health,Sleep 7+ hours,daily,7,7,hours,true,Good sleep,2026-04-02\n"
            "sleep_7h,health,Sleep 8+ hours,daily,7,8,hours,true,Better sleep,2026-04-03\n"
        )
        habits_file.write_text(content, encoding="utf-8")

        result = validate_csv_integrity.validate_csv_schema(habits_file)

        assert not result.passed
        assert "Duplicate ID" in result.errors[0]
        assert "sleep_7h" in result.errors[0]

    def test_validate_csv_schema_empty_required_fields(self) -> None:
        """Test validation catches empty required fields."""
        habits_file = self.test_root / "habits.csv"
        content = (
            "habit_id,area,name,frequency,target_per_week,min_value,unit,active,notes,last_updated\n"
            ",health,Sleep 7+ hours,daily,7,7,hours,true,Good sleep,2026-04-02\n"  # Empty habit_id
        )
        habits_file.write_text(content, encoding="utf-8")

        result = validate_csv_integrity.validate_csv_schema(habits_file)

        assert not result.passed
        assert "Required field 'habit_id' is empty" in result.errors[0]

    def test_validate_csv_schema_invalid_enum_values(self) -> None:
        """Test validation catches invalid enum values."""
        habits_file = self.test_root / "habits.csv"
        content = (
            "habit_id,area,name,frequency,target_per_week,min_value,unit,active,notes,last_updated\n"
            "sleep_7h,health,Sleep 7+ hours,monthly,7,7,hours,maybe,Good sleep,2026-04-02\n"
        )
        habits_file.write_text(content, encoding="utf-8")

        result = validate_csv_integrity.validate_csv_schema(habits_file)

        assert not result.passed
        assert any("Invalid value 'monthly'" in error for error in result.errors)
        assert any("Invalid value 'maybe'" in error for error in result.errors)

    def test_validate_csv_schema_invalid_date_format(self) -> None:
        """Test validation catches invalid date formats."""
        habits_file = self.test_root / "habits.csv"
        content = (
            "habit_id,area,name,frequency,target_per_week,min_value,unit,active,notes,last_updated\n"
            "sleep_7h,health,Sleep 7+ hours,daily,7,7,hours,true,Good sleep,04/02/2026\n"  # Wrong date format
        )
        habits_file.write_text(content, encoding="utf-8")

        result = validate_csv_integrity.validate_csv_schema(habits_file)

        assert not result.passed
        assert "Invalid date format" in result.errors[0]

    def test_validate_csv_schema_invalid_time_format(self) -> None:
        """Test validation catches invalid time formats."""
        time_blocks_file = self.test_root / "time_blocks.csv"
        content = (
            "block_id,date,start,end,title,domain,task_id,source,status,notes\n"
            "block1,2026-04-05,25:30,10:30,Work,work,,manual,planned,Focus time\n"  # Invalid hour
        )
        time_blocks_file.write_text(content, encoding="utf-8")

        result = validate_csv_integrity.validate_csv_schema(time_blocks_file)

        assert not result.passed
        assert any("Invalid time format" in error for error in result.errors)

    def test_validate_csv_schema_encoding_error(self) -> None:
        """Test validation handles encoding errors."""
        habits_file = self.test_root / "habits.csv"
        # Write invalid UTF-8 bytes
        habits_file.write_bytes(b"\xff\xfe")

        result = validate_csv_integrity.validate_csv_schema(habits_file)

        assert not result.passed
        assert "Encoding error" in result.errors[0]


class TestForeignKeyValidation:
    """Test foreign key validation functionality."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_root = Path(self.temp_dir)
        self.canonical_dir = self.test_root / "canonical"
        self.logs_dir = self.test_root / "logs"
        self.canonical_dir.mkdir(parents=True)
        self.logs_dir.mkdir(parents=True)

    def test_validate_foreign_keys_valid_references(self) -> None:
        """Test foreign key validation with valid references."""
        # Create valid project
        projects_content = (
            "project_id,area,name,status,start_date,target_date,description,last_updated,notes,active\n"
            "proj1,health,Morning routine,planning,2026-04-02,,Improve routine,2026-04-02,Focus,true\n"
        )
        (self.canonical_dir / "projects.csv").write_text(
            projects_content, encoding="utf-8"
        )

        # Create task referencing valid project
        tasks_content = (
            "task_id,project_id,title,domain,status,priority,effort_mins,due_date,energy,context,source,next_step,scheduled_date,scheduled_start,scheduled_end,last_updated,notes\n"
            "task1,proj1,Review goals,planning,queued,P3,30,,medium,desk,manual,Start,,,,2026-04-02,Test\n"
        )
        (self.canonical_dir / "tasks.csv").write_text(tasks_content, encoding="utf-8")

        # Create valid habit and daily log
        habits_content = (
            "habit_id,area,name,frequency,target_per_week,min_value,unit,active,notes,last_updated\n"
            "test_habit,health,Test habit,daily,7,1,session,true,Test,2026-04-02\n"
        )
        (self.canonical_dir / "habits.csv").write_text(habits_content, encoding="utf-8")

        daily_log_content = (
            "date,habit_id,value,notes\n2026-04-05,test_habit,1,Test log\n"
        )
        (self.logs_dir / "daily_log.csv").write_text(
            daily_log_content, encoding="utf-8"
        )

        with mock.patch.object(validate_csv_integrity, "LOGS_DIR", self.logs_dir):
            errors = validate_csv_integrity.validate_foreign_keys(self.canonical_dir)
        assert len(errors) == 0

    def test_validate_foreign_keys_invalid_project_reference(self) -> None:
        """Test foreign key validation catches invalid project references."""
        # Create task referencing non-existent project
        tasks_content = (
            "task_id,project_id,title,domain,status,priority,effort_mins,due_date,energy,context,source,next_step,scheduled_date,scheduled_start,scheduled_end,last_updated,notes\n"
            "task1,missing_proj,Review goals,planning,queued,P3,30,,medium,desk,manual,Start,,,,2026-04-02,Test\n"
        )
        (self.canonical_dir / "tasks.csv").write_text(tasks_content, encoding="utf-8")

        with mock.patch.object(validate_csv_integrity, "LOGS_DIR", self.logs_dir):
            errors = validate_csv_integrity.validate_foreign_keys(self.canonical_dir)
        assert len(errors) == 1
        assert "Invalid project_id 'missing_proj'" in errors[0]

    def test_validate_foreign_keys_invalid_task_reference(self) -> None:
        """Test foreign key validation catches invalid task references."""
        # Create time block referencing non-existent task
        time_blocks_content = (
            "block_id,date,start,end,title,domain,task_id,source,status,notes\n"
            "block1,2026-04-05,09:00,10:00,Work,work,missing_task,manual,planned,Focus\n"
        )
        (self.canonical_dir / "time_blocks.csv").write_text(
            time_blocks_content, encoding="utf-8"
        )

        with mock.patch.object(validate_csv_integrity, "LOGS_DIR", self.logs_dir):
            errors = validate_csv_integrity.validate_foreign_keys(self.canonical_dir)
        assert len(errors) == 1
        assert "Invalid task_id 'missing_task'" in errors[0]

    def test_validate_foreign_keys_invalid_habit_reference(self) -> None:
        """Test foreign key validation catches invalid habit references."""
        # Create daily log referencing non-existent habit
        daily_log_content = (
            "date,habit_id,value,notes\n2026-04-05,missing_habit,1,Test log\n"
        )
        (self.logs_dir / "daily_log.csv").write_text(
            daily_log_content, encoding="utf-8"
        )

        with mock.patch.object(validate_csv_integrity, "LOGS_DIR", self.logs_dir):
            errors = validate_csv_integrity.validate_foreign_keys(self.canonical_dir)
        assert len(errors) == 1
        assert "Invalid habit_id 'missing_habit'" in errors[0]

    def test_validate_foreign_keys_missing_files(self) -> None:
        """Test foreign key validation handles missing reference files."""
        # Create task without projects file
        tasks_content = (
            "task_id,project_id,title,domain,status,priority,effort_mins,due_date,energy,context,source,next_step,scheduled_date,scheduled_start,scheduled_end,last_updated,notes\n"
            "task1,proj1,Review goals,planning,queued,P3,30,,medium,desk,manual,Start,,,,2026-04-02,Test\n"
        )
        (self.canonical_dir / "tasks.csv").write_text(tasks_content, encoding="utf-8")

        with mock.patch.object(validate_csv_integrity, "LOGS_DIR", self.logs_dir):
            errors = validate_csv_integrity.validate_foreign_keys(self.canonical_dir)
        # Should error because proj1 project doesn't exist (no projects.csv file)
        assert len(errors) == 1
        assert "Invalid project_id 'proj1'" in errors[0]

    def test_validate_foreign_keys_empty_references(self) -> None:
        """Test foreign key validation ignores empty reference fields."""
        # Create task with empty project_id
        tasks_content = (
            "task_id,project_id,title,domain,status,priority,effort_mins,due_date,energy,context,source,next_step,scheduled_date,scheduled_start,scheduled_end,last_updated,notes\n"
            "task1,,Review goals,planning,queued,P3,30,,medium,desk,manual,Start,,,,2026-04-02,Test\n"
        )
        (self.canonical_dir / "tasks.csv").write_text(tasks_content, encoding="utf-8")

        with mock.patch.object(validate_csv_integrity, "LOGS_DIR", self.logs_dir):
            errors = validate_csv_integrity.validate_foreign_keys(self.canonical_dir)
        assert len(errors) == 0


class TestMainFunction:
    """Test the main validation function."""

    @mock.patch("builtins.print")
    @mock.patch("sys.exit")
    @mock.patch.object(validate_csv_integrity, "validate_csv_schema")
    @mock.patch.object(validate_csv_integrity, "validate_foreign_keys")
    @mock.patch.object(validate_csv_integrity, "CANONICAL_DIR")
    @mock.patch.object(validate_csv_integrity, "LOGS_DIR")
    def test_main_function_success(
        self,
        mock_logs_dir: mock.MagicMock,
        mock_canonical_dir: mock.MagicMock,
        mock_validate_foreign_keys: mock.MagicMock,
        mock_validate_csv_schema: mock.MagicMock,
        mock_exit: mock.MagicMock,
        mock_print: mock.MagicMock,
    ) -> None:
        """Test main function with successful validation."""
        # Mock successful validation
        mock_result = mock.MagicMock()
        mock_result.passed = True
        mock_result.errors = []
        mock_result.warnings = []
        mock_result.relative_to.return_value = Path("test.csv")
        mock_validate_csv_schema.return_value = mock_result
        mock_validate_foreign_keys.return_value = []

        validate_csv_integrity.main()

        # Should not call exit(1)
        mock_exit.assert_not_called()
        # Should print success message
        assert any(
            "All validation checks passed" in str(call)
            for call in mock_print.call_args_list
        )

    @mock.patch("builtins.print")
    @mock.patch("sys.exit")
    @mock.patch.object(validate_csv_integrity, "validate_csv_schema")
    @mock.patch.object(validate_csv_integrity, "validate_foreign_keys")
    @mock.patch.object(validate_csv_integrity, "CANONICAL_DIR")
    @mock.patch.object(validate_csv_integrity, "LOGS_DIR")
    def test_main_function_with_errors(
        self,
        mock_logs_dir: mock.MagicMock,
        mock_canonical_dir: mock.MagicMock,
        mock_validate_foreign_keys: mock.MagicMock,
        mock_validate_csv_schema: mock.MagicMock,
        mock_exit: mock.MagicMock,
        mock_print: mock.MagicMock,
    ) -> None:
        """Test main function with validation errors."""
        # Mock validation with errors
        mock_result = mock.MagicMock()
        mock_result.passed = False
        mock_result.errors = ["Test error"]
        mock_result.warnings = []
        mock_result.relative_to.return_value = Path("test.csv")
        mock_validate_csv_schema.return_value = mock_result
        mock_validate_foreign_keys.return_value = ["Foreign key error"]

        validate_csv_integrity.main()

        # Should call exit(1)
        mock_exit.assert_called_once_with(1)

    @mock.patch("builtins.print")
    @mock.patch("sys.exit")
    @mock.patch.object(validate_csv_integrity, "validate_csv_schema")
    @mock.patch.object(validate_csv_integrity, "validate_foreign_keys")
    @mock.patch.object(validate_csv_integrity, "CANONICAL_DIR")
    @mock.patch.object(validate_csv_integrity, "LOGS_DIR")
    def test_main_function_with_warnings(
        self,
        mock_logs_dir: mock.MagicMock,
        mock_canonical_dir: mock.MagicMock,
        mock_validate_foreign_keys: mock.MagicMock,
        mock_validate_csv_schema: mock.MagicMock,
        mock_exit: mock.MagicMock,
        mock_print: mock.MagicMock,
    ) -> None:
        """Test main function with warnings but no errors (covers lines 592-594)."""
        mock_result = mock.MagicMock()
        mock_result.passed = True
        mock_result.errors = []
        mock_result.warnings = ["Some schema note"]
        mock_result.relative_to.return_value = Path("test.csv")
        mock_validate_csv_schema.return_value = mock_result
        mock_validate_foreign_keys.return_value = []

        validate_csv_integrity.main()

        mock_exit.assert_not_called()
        assert any("WARNING" in str(call) for call in mock_print.call_args_list)


class TestDurationConsistency:
    """Test duration consistency validation (covers lines 277, 280, 284-285, 302-303)."""

    def test_empty_start_time(self) -> None:
        """Empty start time should skip validation (covers line 277)."""
        is_valid, msg = validate_csv_integrity.validate_duration_consistency(
            "", "10:00", "60"
        )
        assert is_valid
        assert msg == ""

    def test_empty_duration(self) -> None:
        """Empty duration should skip validation (covers line 277)."""
        is_valid, msg = validate_csv_integrity.validate_duration_consistency(
            "09:00", "10:00", ""
        )
        assert is_valid
        assert msg == ""

    def test_invalid_time_format_in_duration(self) -> None:
        """Invalid time format should skip validation (covers line 280)."""
        is_valid, msg = validate_csv_integrity.validate_duration_consistency(
            "bad", "10:00", "60"
        )
        assert is_valid
        assert msg == ""

    def test_non_integer_duration(self) -> None:
        """Non-integer duration should skip validation (covers lines 284-285)."""
        is_valid, msg = validate_csv_integrity.validate_duration_consistency(
            "09:00", "10:00", "abc"
        )
        assert is_valid
        assert msg == ""

    def test_matching_duration(self) -> None:
        """Duration matching calculated time should pass."""
        is_valid, msg = validate_csv_integrity.validate_duration_consistency(
            "09:00", "10:00", "60"
        )
        assert is_valid
        assert msg == ""

    def test_mismatching_duration(self) -> None:
        """Duration not matching calculated time should fail."""
        is_valid, msg = validate_csv_integrity.validate_duration_consistency(
            "09:00", "10:00", "120"
        )
        assert not is_valid
        assert "doesn't match" in msg


class TestDateRange:
    """Test date range validation (covers lines 324, 333-334)."""

    def test_invalid_date_format_skips(self) -> None:
        """Invalid date format should skip range validation (covers line 324)."""
        is_valid, msg = validate_csv_integrity.validate_date_range(
            "not-a-date",
            "2026-04-10",
            ("start", "end"),
        )
        assert is_valid
        assert msg == ""

    def test_valid_date_range(self) -> None:
        """Start before end should pass."""
        is_valid, _msg = validate_csv_integrity.validate_date_range(
            "2026-04-01",
            "2026-04-10",
            ("start", "end"),
        )
        assert is_valid

    def test_invalid_date_range(self) -> None:
        """Start after end should fail."""
        is_valid, msg = validate_csv_integrity.validate_date_range(
            "2026-04-10",
            "2026-04-01",
            ("start_date", "target_date"),
        )
        assert not is_valid
        assert "must be before" in msg

    def test_empty_dates_skip(self) -> None:
        """Empty dates should skip validation."""
        is_valid, _msg = validate_csv_integrity.validate_date_range(
            "",
            "2026-04-10",
            ("start", "end"),
        )
        assert is_valid


class TestNumericField:
    """Test numeric field validation."""

    def test_below_minimum(self) -> None:
        is_valid, msg = validate_csv_integrity.validate_numeric_field(
            "0", "target_per_week", min_val=1
        )
        assert not is_valid
        assert "below minimum" in msg

    def test_above_maximum(self) -> None:
        is_valid, msg = validate_csv_integrity.validate_numeric_field(
            "500", "effort_mins", max_val=480
        )
        assert not is_valid
        assert "exceeds maximum" in msg

    def test_invalid_integer(self) -> None:
        is_valid, msg = validate_csv_integrity.validate_numeric_field(
            "abc", "effort_mins", is_integer=True
        )
        assert not is_valid
        assert "not a valid integer" in msg

    def test_invalid_float(self) -> None:
        is_valid, msg = validate_csv_integrity.validate_numeric_field(
            "abc", "metric_target", is_integer=False
        )
        assert not is_valid
        assert "not a valid number" in msg


class TestGenericExceptionHandling:
    """Test generic exception paths in validation (covers line 476-477)."""

    def test_validate_csv_schema_unexpected_error(self) -> None:
        """Test that unexpected errors during row validation are caught (covers lines 476-477)."""
        import csv as _csv

        with tempfile.TemporaryDirectory() as tmp_dir:
            habits_file = Path(tmp_dir) / "habits.csv"
            habits_file.write_text(
                "habit_id,area,name,frequency,target_per_week,min_value,unit,active,notes,last_updated\n"
                "h1,health,Run,daily,7,1,session,true,Notes,2026-04-02\n",
                encoding="utf-8",
            )
            # Patch csv.reader to raise an unexpected exception
            with mock.patch.object(
                _csv, "reader", side_effect=RuntimeError("disk failure")
            ):
                result = validate_csv_integrity.validate_csv_schema(habits_file)
                assert not result.passed
                assert any("Unexpected error" in e for e in result.errors)


class TestForeignKeyExceptionPaths:
    """Test exception handling in foreign key validation (covers lines 498-557)."""

    def setup_method(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.canonical_dir = Path(self.temp_dir) / "canonical"
        self.logs_dir = Path(self.temp_dir) / "logs"
        self.canonical_dir.mkdir(parents=True)
        self.logs_dir.mkdir(parents=True)

    def test_corrupted_projects_file(self) -> None:
        """Exception loading project IDs should be caught (covers lines 498-499)."""
        projects_file = self.canonical_dir / "projects.csv"
        projects_file.write_bytes(b"\xff\xfe invalid utf8")
        with mock.patch.object(validate_csv_integrity, "LOGS_DIR", self.logs_dir):
            errors = validate_csv_integrity.validate_foreign_keys(self.canonical_dir)
        assert any("Failed to load project IDs" in e for e in errors)

    def test_corrupted_tasks_file_loading(self) -> None:
        """Exception loading task IDs should be caught (covers lines 508-509)."""
        tasks_file = self.canonical_dir / "tasks.csv"
        tasks_file.write_bytes(b"\xff\xfe invalid utf8")
        with mock.patch.object(validate_csv_integrity, "LOGS_DIR", self.logs_dir):
            errors = validate_csv_integrity.validate_foreign_keys(self.canonical_dir)
        assert any("Failed to load task IDs" in e for e in errors)

    def test_corrupted_habits_file(self) -> None:
        """Exception loading habit IDs should be caught (covers lines 518-519)."""
        habits_file = self.canonical_dir / "habits.csv"
        habits_file.write_bytes(b"\xff\xfe invalid utf8")
        with mock.patch.object(validate_csv_integrity, "LOGS_DIR", self.logs_dir):
            errors = validate_csv_integrity.validate_foreign_keys(self.canonical_dir)
        assert any("Failed to load habit IDs" in e for e in errors)

    def test_corrupted_tasks_foreign_key_check(self) -> None:
        """Exception loading tasks.csv should be caught and reported."""
        tasks_file = self.canonical_dir / "tasks.csv"
        # Write invalid UTF-8 so the single read fails
        tasks_file.write_bytes(b"\xff\xfe invalid utf8")
        with mock.patch.object(validate_csv_integrity, "LOGS_DIR", self.logs_dir):
            errors = validate_csv_integrity.validate_foreign_keys(
                self.canonical_dir
            )
        assert any("Failed to load task IDs" in e for e in errors)

    def test_corrupted_time_blocks_foreign_key_check(self) -> None:
        """Exception validating time_blocks foreign keys should be caught (covers lines 543-544)."""
        time_blocks_file = self.canonical_dir / "time_blocks.csv"
        time_blocks_file.write_bytes(b"\xff\xfe invalid utf8")
        with mock.patch.object(validate_csv_integrity, "LOGS_DIR", self.logs_dir):
            errors = validate_csv_integrity.validate_foreign_keys(self.canonical_dir)
        assert any("Failed to load time_blocks foreign keys" in e for e in errors)

    def test_corrupted_daily_log_foreign_key_check(self) -> None:
        """Exception validating daily_log foreign keys should be caught (covers lines 556-557)."""
        daily_log_file = self.logs_dir / "daily_log.csv"
        daily_log_file.write_bytes(b"\xff\xfe invalid utf8")
        with mock.patch.object(validate_csv_integrity, "LOGS_DIR", self.logs_dir):
            errors = validate_csv_integrity.validate_foreign_keys(self.canonical_dir)
        assert any("Failed to load daily_log foreign keys" in e for e in errors)


class TestDefensiveExceptionHandlers:
    """Cover defensive except blocks in time/date validation helpers.

    The format validators (validate_time_format, validate_date_format) normally
    prevent invalid strings from reaching strptime. These tests bypass the
    validators to exercise the defensive except blocks.
    """

    def test_validate_time_range_strptime_raises(self) -> None:
        """If strptime raises after format check is bypassed, skip gracefully."""
        with mock.patch.object(
            validate_csv_integrity,
            "validate_time_format",
            return_value=True,
        ):
            is_valid, msg = validate_csv_integrity.validate_time_range(
                "not-a-time", "also-bad"
            )
        assert is_valid is True
        assert msg == ""

    def test_validate_duration_consistency_strptime_raises(self) -> None:
        """If strptime raises during duration check, skip gracefully."""
        with mock.patch.object(
            validate_csv_integrity,
            "validate_time_format",
            return_value=True,
        ):
            is_valid, msg = validate_csv_integrity.validate_duration_consistency(
                "not-a-time", "also-bad", "60"
            )
        assert is_valid is True
        assert msg == ""

    def test_validate_date_range_strptime_raises(self) -> None:
        """If strptime raises during date range check, skip gracefully."""
        with mock.patch.object(
            validate_csv_integrity,
            "validate_date_format",
            return_value=True,
        ):
            is_valid, msg = validate_csv_integrity.validate_date_range(
                "not-a-date", "also-bad", ("start_date", "end_date")
            )
        assert is_valid is True
        assert msg == ""
