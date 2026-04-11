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

    @pytest.mark.parametrize("date_str", ["04-05-2026", "2026/04/05", "invalid", "2026-13-01"])
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
        (self.canonical_dir / "projects.csv").write_text(projects_content, encoding="utf-8")

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
            "date,habit_id,value,notes\n"
            "2026-04-05,test_habit,1,Test log\n"
        )
        (self.logs_dir / "daily_log.csv").write_text(daily_log_content, encoding="utf-8")

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
        (self.canonical_dir / "time_blocks.csv").write_text(time_blocks_content, encoding="utf-8")

        with mock.patch.object(validate_csv_integrity, "LOGS_DIR", self.logs_dir):
            errors = validate_csv_integrity.validate_foreign_keys(self.canonical_dir)
        assert len(errors) == 1
        assert "Invalid task_id 'missing_task'" in errors[0]

    def test_validate_foreign_keys_invalid_habit_reference(self) -> None:
        """Test foreign key validation catches invalid habit references."""
        # Create daily log referencing non-existent habit
        daily_log_content = (
            "date,habit_id,value,notes\n"
            "2026-04-05,missing_habit,1,Test log\n"
        )
        (self.logs_dir / "daily_log.csv").write_text(daily_log_content, encoding="utf-8")

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
    @mock.patch("builtins.exit")
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
        assert any("All validation checks passed" in str(call) for call in mock_print.call_args_list)

    @mock.patch("builtins.print")
    @mock.patch("builtins.exit")
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
