#!/usr/bin/env python3
"""Comprehensive tests for validate_csv_integrity.py module."""

from __future__ import annotations

import csv
import tempfile
import pytest
from pathlib import Path
from unittest import mock
from importlib.util import spec_from_file_location, module_from_spec

# Import the module under test
REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "01-ops" / "life-os" / "scripts" / "validate_csv_integrity.py"
SPEC = spec_from_file_location("validate_csv_integrity", MODULE_PATH)
validate_csv_integrity = module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(validate_csv_integrity)


class TestValidationResult:
    """Test the ValidationResult class."""

    def test_initialization(self):
        """Test ValidationResult initialization."""
        file_path = Path("/test/file.csv")
        result = validate_csv_integrity.ValidationResult(file_path)

        assert result.file_path == file_path
        assert result.errors == []
        assert result.warnings == []
        assert result.passed is True

    def test_add_error(self):
        """Test adding errors to ValidationResult."""
        result = validate_csv_integrity.ValidationResult(Path("test.csv"))

        result.add_error("Test error message")

        assert len(result.errors) == 1
        assert result.errors[0] == "Test error message"
        assert result.passed is False

    def test_add_multiple_errors(self):
        """Test adding multiple errors."""
        result = validate_csv_integrity.ValidationResult(Path("test.csv"))

        result.add_error("Error 1")
        result.add_error("Error 2")

        assert len(result.errors) == 2
        assert result.errors == ["Error 1", "Error 2"]
        assert result.passed is False

    def test_add_warning(self):
        """Test adding warnings to ValidationResult."""
        result = validate_csv_integrity.ValidationResult(Path("test.csv"))

        result.add_warning("Test warning message")

        assert len(result.warnings) == 1
        assert result.warnings[0] == "Test warning message"
        assert result.passed is True  # Warnings don't affect passed status

    def test_add_warning_and_error(self):
        """Test adding both warnings and errors."""
        result = validate_csv_integrity.ValidationResult(Path("test.csv"))

        result.add_warning("Warning message")
        result.add_error("Error message")

        assert len(result.warnings) == 1
        assert len(result.errors) == 1
        assert result.passed is False


class TestDateValidation:
    """Test date validation functions."""

    def test_validate_date_format_valid_dates(self):
        """Test validation with valid date formats."""
        valid_dates = [
            "2026-04-05",
            "2025-12-31",
            "2000-01-01",
            "2024-02-29",  # Leap year
        ]

        for date in valid_dates:
            assert validate_csv_integrity.validate_date_format(date) is True

    def test_validate_date_format_invalid_dates(self):
        """Test validation with invalid date formats."""
        invalid_dates = [
            "2026/04/05",    # Wrong separator
            "04-05-2026",    # Wrong order
            "2026-13-01",    # Invalid month
            "2026-02-30",    # Invalid day for February
            "not-a-date",    # Text
            "2026-04",       # Incomplete
            "2026-04-05T10:30:00",  # With time
        ]

        for date in invalid_dates:
            assert validate_csv_integrity.validate_date_format(date) is False

    def test_validate_date_format_permissive_dates(self):
        """Test that date validation is permissive for some formats."""
        # These are accepted by datetime.strptime even though they're not ideal
        permissive_dates = [
            "2026-4-5",      # Missing leading zeros (strptime accepts this)
        ]

        for date in permissive_dates:
            assert validate_csv_integrity.validate_date_format(date) is True

    def test_validate_date_format_empty_string(self):
        """Test validation with empty strings (should be allowed)."""
        assert validate_csv_integrity.validate_date_format("") is True
        assert validate_csv_integrity.validate_date_format("   ") is True

    def test_validate_date_format_whitespace(self):
        """Test validation with whitespace around dates."""
        # The function checks .strip() for emptiness but parses the original string
        # So " 2026-04-05 " will fail parsing because strptime doesn't like leading/trailing spaces
        assert validate_csv_integrity.validate_date_format(" 2026-04-05 ") is False
        # But pure spaces should be treated as empty and return True
        assert validate_csv_integrity.validate_date_format("   ") is True


class TestTimeValidation:
    """Test time validation functions."""

    def test_validate_time_format_valid_times(self):
        """Test validation with valid time formats."""
        valid_times = [
            "09:30",
            "23:59",
            "00:00",
            "12:00",
            "1:30",      # Single digit hour
            "01:05",     # Leading zeros
        ]

        for time in valid_times:
            assert validate_csv_integrity.validate_time_format(time) is True

    def test_validate_time_format_invalid_times(self):
        """Test validation with invalid time formats."""
        invalid_times = [
            "24:00",     # Invalid hour
            "12:60",     # Invalid minute
            "9:5",       # Missing leading zero on minute
            "09:30:00",  # With seconds
            "9:30 AM",   # With AM/PM
            "not-time",  # Text
            "09",        # Hour only
            ":30",       # Missing hour
        ]

        for time in invalid_times:
            assert validate_csv_integrity.validate_time_format(time) is False

    def test_validate_time_format_empty_string(self):
        """Test validation with empty strings (should be allowed)."""
        assert validate_csv_integrity.validate_time_format("") is True
        assert validate_csv_integrity.validate_time_format("   ") is True


class TestCSVSchemaValidation:
    """Test CSV schema validation functionality."""

    def setup_method(self):
        """Set up test environment for each test method."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def teardown_method(self):
        """Clean up after each test method."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def create_test_csv(self, filename: str, headers: list, data_rows: list = None) -> Path:
        """Helper to create test CSV files."""
        csv_path = self.temp_path / filename

        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            if data_rows:
                writer.writerows(data_rows)

        return csv_path

    def test_validate_csv_schema_file_not_exists(self):
        """Test validation when file doesn't exist."""
        non_existent = self.temp_path / "missing.csv"
        result = validate_csv_integrity.validate_csv_schema(non_existent)

        assert not result.passed
        assert len(result.errors) == 1
        assert "does not exist" in result.errors[0]

    def test_validate_csv_schema_unknown_file(self):
        """Test validation for unknown file type."""
        unknown_csv = self.create_test_csv("unknown.csv", ["col1", "col2"])
        result = validate_csv_integrity.validate_csv_schema(unknown_csv)

        assert result.passed
        assert len(result.warnings) == 1
        assert "No schema definition found" in result.warnings[0]

    def test_validate_csv_schema_empty_file(self):
        """Test validation of empty CSV file."""
        csv_path = self.temp_path / "tasks.csv"
        csv_path.write_text("", encoding="utf-8")

        result = validate_csv_integrity.validate_csv_schema(csv_path)

        assert not result.passed
        assert len(result.errors) == 1
        assert "empty or has no headers" in result.errors[0]

    def test_validate_csv_schema_valid_tasks_file(self):
        """Test validation of valid tasks.csv file."""
        expected_headers = validate_csv_integrity.EXPECTED_SCHEMAS["tasks.csv"]
        data_row = [
            "task123", "Test Task", "work", "proj1", "queued", "3",
            "60", "2026-04-10", "medium", "office", "manual", "Start work",
            "2026-04-06", "09:00", "10:00", "2026-04-05", "Test notes"
        ]

        csv_path = self.create_test_csv("tasks.csv", expected_headers, [data_row])
        result = validate_csv_integrity.validate_csv_schema(csv_path)

        assert result.passed
        assert len(result.errors) == 0

    def test_validate_csv_schema_wrong_headers(self):
        """Test validation with incorrect headers."""
        wrong_headers = ["wrong", "headers", "here"]
        csv_path = self.create_test_csv("tasks.csv", wrong_headers)

        result = validate_csv_integrity.validate_csv_schema(csv_path)

        assert not result.passed
        assert len(result.errors) == 1
        assert "Schema mismatch" in result.errors[0]

    def test_validate_csv_schema_wrong_column_count(self):
        """Test validation with wrong number of columns in data row."""
        expected_headers = validate_csv_integrity.EXPECTED_SCHEMAS["tasks.csv"]
        short_data_row = ["task123", "Test Task"]  # Missing most columns

        csv_path = self.create_test_csv("tasks.csv", expected_headers, [short_data_row])
        result = validate_csv_integrity.validate_csv_schema(csv_path)

        assert not result.passed
        assert len(result.errors) == 1
        assert "has 2 columns, expected" in result.errors[0]

    def test_validate_csv_schema_duplicate_ids(self):
        """Test validation with duplicate IDs."""
        expected_headers = validate_csv_integrity.EXPECTED_SCHEMAS["tasks.csv"]
        data_rows = [
            ["task123", "Task 1", "work", "", "queued", "1", "", "", "", "", "", "", "", "", "", "", ""],
            ["task123", "Task 2", "work", "", "queued", "2", "", "", "", "", "", "", "", "", "", "", ""]  # Duplicate ID
        ]

        csv_path = self.create_test_csv("tasks.csv", expected_headers, data_rows)
        result = validate_csv_integrity.validate_csv_schema(csv_path)

        assert not result.passed
        assert len(result.errors) == 1
        assert "Duplicate ID 'task123'" in result.errors[0]

    def test_validate_csv_schema_required_fields_empty(self):
        """Test validation with empty required fields."""
        expected_headers = validate_csv_integrity.EXPECTED_SCHEMAS["tasks.csv"]
        data_row = [
            "", "Test Task", "", "", "", "",  # Empty task_id, domain
            "", "", "", "", "", "", "", "", "", "", ""
        ]

        csv_path = self.create_test_csv("tasks.csv", expected_headers, [data_row])
        result = validate_csv_integrity.validate_csv_schema(csv_path)

        assert not result.passed
        assert len(result.errors) >= 2
        # Should have errors for empty task_id and domain
        error_messages = " ".join(result.errors)
        assert "task_id" in error_messages
        assert "domain" in error_messages

    def test_validate_csv_schema_invalid_enum_values(self):
        """Test validation with invalid enum values."""
        expected_headers = validate_csv_integrity.EXPECTED_SCHEMAS["tasks.csv"]
        data_row = [
            "task123", "Test Task", "work", "", "invalid_status", "10",  # Invalid status and priority
            "", "", "invalid_energy", "", "", "", "", "", "", "", ""
        ]

        csv_path = self.create_test_csv("tasks.csv", expected_headers, [data_row])
        result = validate_csv_integrity.validate_csv_schema(csv_path)

        assert not result.passed
        assert len(result.errors) >= 2
        error_messages = " ".join(result.errors)
        assert "invalid_status" in error_messages
        assert "invalid_energy" in error_messages

    def test_validate_csv_schema_invalid_date_format(self):
        """Test validation with invalid date formats."""
        expected_headers = validate_csv_integrity.EXPECTED_SCHEMAS["tasks.csv"]
        data_row = [
            "task123", "Test Task", "work", "", "queued", "1",
            "", "invalid-date", "", "", "", "", "2026/04/05", "", "", "bad-date", ""
        ]

        csv_path = self.create_test_csv("tasks.csv", expected_headers, [data_row])
        result = validate_csv_integrity.validate_csv_schema(csv_path)

        assert not result.passed
        error_messages = " ".join(result.errors)
        assert "Invalid date format" in error_messages

    def test_validate_csv_schema_invalid_time_format(self):
        """Test validation with invalid time formats."""
        expected_headers = validate_csv_integrity.EXPECTED_SCHEMAS["time_blocks.csv"]
        data_row = [
            "block123", "2026-04-05", "25:00", "12:70", "Test Block",
            "work", "", "", "", ""
        ]

        csv_path = self.create_test_csv("time_blocks.csv", expected_headers, [data_row])
        result = validate_csv_integrity.validate_csv_schema(csv_path)

        assert not result.passed
        error_messages = " ".join(result.errors)
        assert "Invalid time format" in error_messages

    def test_validate_csv_schema_encoding_error(self):
        """Test handling of encoding errors."""
        csv_path = self.temp_path / "tasks.csv"

        # Write binary data that will cause encoding issues
        with csv_path.open("wb") as f:
            f.write(b"\x80\x81\x82invalid,utf8,data\n")

        result = validate_csv_integrity.validate_csv_schema(csv_path)

        assert not result.passed
        assert len(result.errors) == 1
        assert "Encoding error" in result.errors[0]


class TestForeignKeyValidation:
    """Test foreign key validation functionality."""

    def setup_method(self):
        """Set up test environment for each test method."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_canonical_dir = Path(self.temp_dir) / "canonical"
        self.temp_logs_dir = Path(self.temp_dir) / "logs"
        self.temp_canonical_dir.mkdir()
        self.temp_logs_dir.mkdir()

    def teardown_method(self):
        """Clean up after each test method."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def create_test_csv(self, directory: Path, filename: str, headers: list, data_rows: list = None) -> Path:
        """Helper to create test CSV files."""
        csv_path = directory / filename

        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            if data_rows:
                writer.writerows(data_rows)

        return csv_path

    def test_validate_foreign_keys_no_errors(self):
        """Test foreign key validation with valid references."""
        # Create projects.csv
        project_headers = validate_csv_integrity.EXPECTED_SCHEMAS["projects.csv"]
        project_data = [["proj1", "work", "Test Project", "active", "", "", "", "", "", "true"]]
        self.create_test_csv(self.temp_canonical_dir, "projects.csv", project_headers, project_data)

        # Create tasks.csv with valid project reference
        task_headers = validate_csv_integrity.EXPECTED_SCHEMAS["tasks.csv"]
        task_data = [["task1", "Test Task", "work", "proj1", "queued", "1", "", "", "", "", "", "", "", "", "", "", ""]]
        self.create_test_csv(self.temp_canonical_dir, "tasks.csv", task_headers, task_data)

        # Create habits.csv
        habit_headers = validate_csv_integrity.EXPECTED_SCHEMAS["habits.csv"]
        habit_data = [["habit1", "health", "Exercise", "daily", "7", "1", "times", "true", "", ""]]
        self.create_test_csv(self.temp_canonical_dir, "habits.csv", habit_headers, habit_data)

        # Create time_blocks.csv with valid task reference
        time_block_headers = validate_csv_integrity.EXPECTED_SCHEMAS["time_blocks.csv"]
        time_block_data = [["block1", "2026-04-05", "09:00", "10:00", "Test Block", "work", "task1", "manual", "planned", ""]]
        self.create_test_csv(self.temp_canonical_dir, "time_blocks.csv", time_block_headers, time_block_data)

        # Create daily_log.csv with valid habit reference
        daily_log_headers = validate_csv_integrity.EXPECTED_SCHEMAS["daily_log.csv"]
        daily_log_data = [["2026-04-05", "habit1", "1", ""]]
        self.create_test_csv(self.temp_logs_dir, "daily_log.csv", daily_log_headers, daily_log_data)

        # Mock the LOGS_DIR to point to our temp logs directory
        with mock.patch.object(validate_csv_integrity, "LOGS_DIR", self.temp_logs_dir):
            errors = validate_csv_integrity.validate_foreign_keys(self.temp_canonical_dir)

        assert len(errors) == 0

    def test_validate_foreign_keys_invalid_project_reference(self):
        """Test foreign key validation with invalid project reference."""
        # Create projects.csv
        project_headers = validate_csv_integrity.EXPECTED_SCHEMAS["projects.csv"]
        project_data = [["proj1", "work", "Test Project", "active", "", "", "", "", "", "true"]]
        self.create_test_csv(self.temp_canonical_dir, "projects.csv", project_headers, project_data)

        # Create tasks.csv with invalid project reference
        task_headers = validate_csv_integrity.EXPECTED_SCHEMAS["tasks.csv"]
        task_data = [["task1", "Test Task", "work", "invalid_proj", "queued", "1", "", "", "", "", "", "", "", "", "", "", ""]]
        self.create_test_csv(self.temp_canonical_dir, "tasks.csv", task_headers, task_data)

        # Create empty daily_log.csv so it doesn't interfere
        daily_log_headers = validate_csv_integrity.EXPECTED_SCHEMAS["daily_log.csv"]
        self.create_test_csv(self.temp_logs_dir, "daily_log.csv", daily_log_headers, [])

        # Mock the LOGS_DIR to point to our temp logs directory
        with mock.patch.object(validate_csv_integrity, "LOGS_DIR", self.temp_logs_dir):
            errors = validate_csv_integrity.validate_foreign_keys(self.temp_canonical_dir)

        assert len(errors) == 1
        assert "Invalid project_id 'invalid_proj'" in errors[0]

    def test_validate_foreign_keys_invalid_task_reference(self):
        """Test foreign key validation with invalid task reference in time_blocks."""
        # Create tasks.csv
        task_headers = validate_csv_integrity.EXPECTED_SCHEMAS["tasks.csv"]
        task_data = [["task1", "Test Task", "work", "", "queued", "1", "", "", "", "", "", "", "", "", "", "", ""]]
        self.create_test_csv(self.temp_canonical_dir, "tasks.csv", task_headers, task_data)

        # Create time_blocks.csv with invalid task reference
        time_block_headers = validate_csv_integrity.EXPECTED_SCHEMAS["time_blocks.csv"]
        time_block_data = [["block1", "2026-04-05", "09:00", "10:00", "Test Block", "work", "invalid_task", "manual", "planned", ""]]
        self.create_test_csv(self.temp_canonical_dir, "time_blocks.csv", time_block_headers, time_block_data)

        # Create empty daily_log.csv so it doesn't interfere
        daily_log_headers = validate_csv_integrity.EXPECTED_SCHEMAS["daily_log.csv"]
        self.create_test_csv(self.temp_logs_dir, "daily_log.csv", daily_log_headers, [])

        # Mock the LOGS_DIR to point to our temp logs directory
        with mock.patch.object(validate_csv_integrity, "LOGS_DIR", self.temp_logs_dir):
            errors = validate_csv_integrity.validate_foreign_keys(self.temp_canonical_dir)

        assert len(errors) == 1
        assert "Invalid task_id 'invalid_task'" in errors[0]

    def test_validate_foreign_keys_invalid_habit_reference(self):
        """Test foreign key validation with invalid habit reference in daily_log."""
        # Create habits.csv
        habit_headers = validate_csv_integrity.EXPECTED_SCHEMAS["habits.csv"]
        habit_data = [["habit1", "health", "Exercise", "daily", "7", "1", "times", "true", "", ""]]
        self.create_test_csv(self.temp_canonical_dir, "habits.csv", habit_headers, habit_data)

        # Create daily_log.csv with invalid habit reference
        daily_log_headers = validate_csv_integrity.EXPECTED_SCHEMAS["daily_log.csv"]
        daily_log_data = [["2026-04-05", "invalid_habit", "1", ""]]
        self.create_test_csv(self.temp_logs_dir, "daily_log.csv", daily_log_headers, daily_log_data)

        # Mock the LOGS_DIR to point to our temp logs directory
        with mock.patch.object(validate_csv_integrity, "LOGS_DIR", self.temp_logs_dir):
            errors = validate_csv_integrity.validate_foreign_keys(self.temp_canonical_dir)

        assert len(errors) == 1
        assert "Invalid habit_id 'invalid_habit'" in errors[0]

    def test_validate_foreign_keys_missing_files(self):
        """Test foreign key validation when reference files are missing."""
        # Create tasks.csv without projects.csv
        task_headers = validate_csv_integrity.EXPECTED_SCHEMAS["tasks.csv"]
        task_data = [["task1", "Test Task", "work", "proj1", "queued", "1", "", "", "", "", "", "", "", "", "", "", ""]]
        self.create_test_csv(self.temp_canonical_dir, "tasks.csv", task_headers, task_data)

        # Create empty daily_log.csv so it doesn't interfere
        daily_log_headers = validate_csv_integrity.EXPECTED_SCHEMAS["daily_log.csv"]
        self.create_test_csv(self.temp_logs_dir, "daily_log.csv", daily_log_headers, [])

        # Mock the LOGS_DIR to point to our temp logs directory
        with mock.patch.object(validate_csv_integrity, "LOGS_DIR", self.temp_logs_dir):
            errors = validate_csv_integrity.validate_foreign_keys(self.temp_canonical_dir)

        # Should have errors for missing project validation since tasks.csv references proj1 but projects.csv doesn't exist
        assert len(errors) == 1
        assert "Invalid project_id 'proj1'" in errors[0]

    def test_validate_foreign_keys_empty_references(self):
        """Test foreign key validation with empty reference fields."""
        # Create projects.csv
        project_headers = validate_csv_integrity.EXPECTED_SCHEMAS["projects.csv"]
        project_data = [["proj1", "work", "Test Project", "active", "", "", "", "", "", "true"]]
        self.create_test_csv(self.temp_canonical_dir, "projects.csv", project_headers, project_data)

        # Create tasks.csv with empty project_id (should be allowed)
        task_headers = validate_csv_integrity.EXPECTED_SCHEMAS["tasks.csv"]
        task_data = [["task1", "Test Task", "work", "", "queued", "1", "", "", "", "", "", "", "", "", "", "", ""]]
        self.create_test_csv(self.temp_canonical_dir, "tasks.csv", task_headers, task_data)

        # Create empty daily_log.csv so it doesn't interfere
        daily_log_headers = validate_csv_integrity.EXPECTED_SCHEMAS["daily_log.csv"]
        self.create_test_csv(self.temp_logs_dir, "daily_log.csv", daily_log_headers, [])

        # Mock the LOGS_DIR to point to our temp logs directory
        with mock.patch.object(validate_csv_integrity, "LOGS_DIR", self.temp_logs_dir):
            errors = validate_csv_integrity.validate_foreign_keys(self.temp_canonical_dir)

        assert len(errors) == 0

    def test_validate_foreign_keys_file_read_error(self):
        """Test foreign key validation with file read errors."""
        # Create a projects.csv file that exists but causes read errors
        csv_path = self.temp_canonical_dir / "projects.csv"
        csv_path.write_text("col1,col2\nval1,val2\n", encoding="utf-8")

        # Create empty daily_log.csv so it doesn't interfere
        daily_log_headers = validate_csv_integrity.EXPECTED_SCHEMAS["daily_log.csv"]
        self.create_test_csv(self.temp_logs_dir, "daily_log.csv", daily_log_headers, [])

        # Mock Path.open() method to raise PermissionError when opening projects.csv
        def mock_open_side_effect(*args, **kwargs):
            # Only raise error for the projects.csv file path
            calling_self = args[0] if args else None
            if isinstance(calling_self, Path) and calling_self.name == "projects.csv":
                raise PermissionError("Access denied")
            # For other files, use the real open method
            return Path.open(calling_self, *args[1:], **kwargs)

        with mock.patch.object(Path, "open", side_effect=mock_open_side_effect), \
             mock.patch.object(validate_csv_integrity, "LOGS_DIR", self.temp_logs_dir):
            errors = validate_csv_integrity.validate_foreign_keys(self.temp_canonical_dir)

        # Should have an error about failing to load project IDs
        assert len(errors) >= 1
        error_messages = " ".join(errors)
        assert "Failed to load project IDs" in error_messages


class TestMainFunction:
    """Test the main function and integration."""

    def test_main_function_exists(self):
        """Test that main function exists and is callable."""
        assert callable(validate_csv_integrity.main)

    def test_main_function_with_mock_data(self):
        """Test main function with mocked data and paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_canonical_dir = Path(temp_dir) / "canonical"
            temp_logs_dir = Path(temp_dir) / "logs"
            temp_repo_root = Path(temp_dir)  # Mock repo root
            temp_canonical_dir.mkdir()
            temp_logs_dir.mkdir()

            # Create minimal valid CSV files
            for filename in ["habits.csv", "goals.csv", "tasks.csv", "projects.csv",
                           "time_blocks.csv", "time_logs.csv", "calendar_events.csv"]:
                headers = validate_csv_integrity.EXPECTED_SCHEMAS[filename]
                csv_path = temp_canonical_dir / filename
                with csv_path.open("w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)

            # Create log files
            for filename in ["daily_log.csv", "activity_log.csv"]:
                headers = validate_csv_integrity.EXPECTED_SCHEMAS[filename]
                csv_path = temp_logs_dir / filename
                with csv_path.open("w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)

            # Mock the directories and repo root to point to our temp directories
            with mock.patch.object(validate_csv_integrity, "CANONICAL_DIR", temp_canonical_dir), \
                 mock.patch.object(validate_csv_integrity, "LOGS_DIR", temp_logs_dir), \
                 mock.patch.object(validate_csv_integrity, "REPO_ROOT", temp_repo_root), \
                 mock.patch("sys.exit") as mock_exit:

                # Capture stdout to avoid printing during tests
                with mock.patch("builtins.print"):
                    validate_csv_integrity.main()

                # Should not call sys.exit(1) since all validation should pass
                mock_exit.assert_not_called()


class TestConstants:
    """Test that constants and schemas are properly defined."""

    def test_expected_schemas_defined(self):
        """Test that all expected schemas are defined."""
        expected_files = [
            "habits.csv", "goals.csv", "tasks.csv", "projects.csv",
            "time_blocks.csv", "time_logs.csv", "calendar_events.csv",
            "daily_log.csv", "activity_log.csv"
        ]

        for filename in expected_files:
            assert filename in validate_csv_integrity.EXPECTED_SCHEMAS
            assert isinstance(validate_csv_integrity.EXPECTED_SCHEMAS[filename], list)
            assert len(validate_csv_integrity.EXPECTED_SCHEMAS[filename]) > 0

    def test_required_fields_defined(self):
        """Test that required fields are properly defined."""
        for filename in validate_csv_integrity.REQUIRED_FIELDS:
            assert isinstance(validate_csv_integrity.REQUIRED_FIELDS[filename], set)

    def test_enum_fields_defined(self):
        """Test that enum fields are properly defined."""
        for filename in validate_csv_integrity.ENUM_FIELDS:
            assert isinstance(validate_csv_integrity.ENUM_FIELDS[filename], dict)

    def test_id_fields_defined(self):
        """Test that ID fields are properly defined."""
        for filename in validate_csv_integrity.ID_FIELDS:
            id_field = validate_csv_integrity.ID_FIELDS[filename]
            assert isinstance(id_field, str)
            assert id_field in validate_csv_integrity.EXPECTED_SCHEMAS[filename]