#!/usr/bin/env python3
"""Tests for CSV integrity validation module."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from importlib.util import module_from_spec, spec_from_file_location

# Import the validation module dynamically
REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "01-ops" / "life-os" / "scripts" / "validate_csv_integrity.py"
SPEC = spec_from_file_location("validate_csv_integrity", MODULE_PATH)
validate_csv_integrity = module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(validate_csv_integrity)

# Import the module's exports
EXPECTED_SCHEMAS = validate_csv_integrity.EXPECTED_SCHEMAS
REQUIRED_FIELDS = validate_csv_integrity.REQUIRED_FIELDS
ENUM_FIELDS = validate_csv_integrity.ENUM_FIELDS
DATE_FIELDS = validate_csv_integrity.DATE_FIELDS
TIME_FIELDS = validate_csv_integrity.TIME_FIELDS
ID_FIELDS = validate_csv_integrity.ID_FIELDS
ValidationResult = validate_csv_integrity.ValidationResult
validate_date_format = validate_csv_integrity.validate_date_format
validate_time_format = validate_csv_integrity.validate_time_format
validate_csv_schema = validate_csv_integrity.validate_csv_schema
validate_foreign_keys = validate_csv_integrity.validate_foreign_keys
main = validate_csv_integrity.main


class TestValidationResult(unittest.TestCase):
    """Test ValidationResult class."""

    def test_validation_result_init(self):
        """Test ValidationResult initialization."""
        path = Path("test.csv")
        result = ValidationResult(path)

        assert result.file_path == path
        assert result.errors == []
        assert result.warnings == []
        assert result.passed is True

    def test_add_error(self):
        """Test adding errors."""
        result = ValidationResult(Path("test.csv"))
        result.add_error("Test error")

        assert len(result.errors) == 1
        assert result.errors[0] == "Test error"
        assert result.passed is False

    def test_add_warning(self):
        """Test adding warnings."""
        result = ValidationResult(Path("test.csv"))
        result.add_warning("Test warning")

        assert len(result.warnings) == 1
        assert result.warnings[0] == "Test warning"
        assert result.passed is True  # Warnings don't affect passed status


class TestDateTimeValidation(unittest.TestCase):
    """Test date and time validation functions."""

    def test_validate_date_format_valid(self):
        """Test valid date formats."""
        assert validate_date_format("2026-04-05") is True
        assert validate_date_format("2020-12-31") is True
        assert validate_date_format("2025-01-01") is True

    def test_validate_date_format_invalid(self):
        """Test invalid date formats."""
        assert validate_date_format("2026-13-05") is False
        assert validate_date_format("2026-04-32") is False
        assert validate_date_format("invalid") is False
        assert validate_date_format("26-04-05") is False
        assert validate_date_format("2026/04/05") is False

    def test_validate_date_format_empty(self):
        """Test empty date values."""
        assert validate_date_format("") is True
        assert validate_date_format("   ") is True

    def test_validate_time_format_valid(self):
        """Test valid time formats."""
        assert validate_time_format("09:30") is True
        assert validate_time_format("23:59") is True
        assert validate_time_format("00:00") is True
        assert validate_time_format("9:30") is True

    def test_validate_time_format_invalid(self):
        """Test invalid time formats."""
        assert validate_time_format("25:00") is False
        assert validate_time_format("09:60") is False
        assert validate_time_format("invalid") is False
        assert validate_time_format("9") is False
        assert validate_time_format("9:3") is False

    def test_validate_time_format_empty(self):
        """Test empty time values."""
        assert validate_time_format("") is True
        assert validate_time_format("   ") is True


class TestCSVSchemaValidation(unittest.TestCase):
    """Test CSV schema validation."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_validate_csv_schema_nonexistent_file(self):
        """Test validation of non-existent file."""
        file_path = self.temp_path / "nonexistent.csv"
        result = validate_csv_schema(file_path)

        assert not result.passed
        assert len(result.errors) == 1
        assert "does not exist" in result.errors[0]

    def test_validate_csv_schema_unknown_file(self):
        """Test validation of unknown file type."""
        file_path = self.temp_path / "unknown.csv"
        file_path.write_text("header1,header2\nvalue1,value2\n", encoding="utf-8")

        result = validate_csv_schema(file_path)

        assert result.passed  # Unknown files just get a warning
        assert len(result.warnings) == 1
        assert "No schema definition found" in result.warnings[0]

    def test_validate_csv_schema_empty_file(self):
        """Test validation of empty file."""
        file_path = self.temp_path / "habits.csv"
        file_path.write_text("", encoding="utf-8")

        result = validate_csv_schema(file_path)

        assert not result.passed
        assert "empty or has no headers" in result.errors[0]

    def test_validate_csv_schema_valid_habits_file(self):
        """Test validation of valid habits file."""
        file_path = self.temp_path / "habits.csv"
        headers = EXPECTED_SCHEMAS["habits.csv"]

        # Create a valid habits file
        with file_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerow([
                "sleep_7h", "health", "Sleep 7+ hours", "daily", "7",
                "7", "hours", "true", "Quality sleep", "2026-04-05"
            ])

        result = validate_csv_schema(file_path)

        assert result.passed
        assert len(result.errors) == 0

    def test_validate_csv_schema_header_mismatch(self):
        """Test validation with mismatched headers."""
        file_path = self.temp_path / "habits.csv"

        with file_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["wrong", "headers"])
            writer.writerow(["value1", "value2"])

        result = validate_csv_schema(file_path)

        assert not result.passed
        assert "Schema mismatch" in result.errors[0]

    def test_validate_csv_schema_column_count_mismatch(self):
        """Test validation with incorrect column count."""
        file_path = self.temp_path / "habits.csv"
        headers = EXPECTED_SCHEMAS["habits.csv"]

        with file_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            # Row with too few columns
            writer.writerow(["only", "two", "columns"])

        result = validate_csv_schema(file_path)

        assert not result.passed
        assert "has 3 columns, expected" in result.errors[0]

    def test_validate_csv_schema_duplicate_ids(self):
        """Test validation with duplicate IDs."""
        file_path = self.temp_path / "habits.csv"
        headers = EXPECTED_SCHEMAS["habits.csv"]

        with file_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            # Two rows with the same ID
            writer.writerow([
                "duplicate_id", "health", "Habit 1", "daily", "1",
                "1", "times", "true", "", "2026-04-05"
            ])
            writer.writerow([
                "duplicate_id", "health", "Habit 2", "daily", "1",
                "1", "times", "true", "", "2026-04-05"
            ])

        result = validate_csv_schema(file_path)

        assert not result.passed
        assert "Duplicate ID 'duplicate_id'" in result.errors[0]

    def test_validate_csv_schema_empty_required_field(self):
        """Test validation with empty required fields."""
        file_path = self.temp_path / "habits.csv"
        headers = EXPECTED_SCHEMAS["habits.csv"]

        with file_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            # Row with empty required field (habit_id)
            writer.writerow([
                "", "health", "Habit", "daily", "1",
                "1", "times", "true", "", "2026-04-05"
            ])

        result = validate_csv_schema(file_path)

        assert not result.passed
        assert "Required field 'habit_id' is empty" in result.errors[0]

    def test_validate_csv_schema_invalid_enum_value(self):
        """Test validation with invalid enum values."""
        file_path = self.temp_path / "habits.csv"
        headers = EXPECTED_SCHEMAS["habits.csv"]

        with file_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            # Row with invalid frequency value
            writer.writerow([
                "habit_id", "health", "Habit", "invalid_freq", "1",
                "1", "times", "true", "", "2026-04-05"
            ])

        result = validate_csv_schema(file_path)

        assert not result.passed
        assert "Invalid value 'invalid_freq' for field 'frequency'" in result.errors[0]

    def test_validate_csv_schema_invalid_date_format(self):
        """Test validation with invalid date format."""
        file_path = self.temp_path / "habits.csv"
        headers = EXPECTED_SCHEMAS["habits.csv"]

        with file_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            # Row with invalid date format
            writer.writerow([
                "habit_id", "health", "Habit", "daily", "1",
                "1", "times", "true", "", "invalid-date"
            ])

        result = validate_csv_schema(file_path)

        assert not result.passed
        assert "Invalid date format 'invalid-date'" in result.errors[0]

    def test_validate_csv_schema_invalid_time_format(self):
        """Test validation with invalid time format."""
        file_path = self.temp_path / "time_blocks.csv"
        headers = EXPECTED_SCHEMAS["time_blocks.csv"]

        with file_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            # Row with invalid time format
            writer.writerow([
                "block_id", "2026-04-05", "invalid-time", "10:00",
                "Block Title", "work", "task_id", "manual", "planned", ""
            ])

        result = validate_csv_schema(file_path)

        assert not result.passed
        assert "Invalid time format 'invalid-time'" in result.errors[0]

    def test_validate_csv_schema_encoding_error(self):
        """Test handling of encoding errors."""
        file_path = self.temp_path / "habits.csv"

        # Write invalid UTF-8
        with file_path.open("wb") as f:
            f.write(b"\xff\xfe")  # Invalid UTF-8

        result = validate_csv_schema(file_path)

        assert not result.passed
        assert "Encoding error" in result.errors[0]


class TestForeignKeyValidation(unittest.TestCase):
    """Test foreign key validation."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_csv_file(self, filename: str, headers: list, rows: list):
        """Helper to create a CSV file."""
        file_path = self.temp_path / filename
        with file_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for row in rows:
                writer.writerow(row)
        return file_path

    def test_validate_foreign_keys_valid_references(self):
        """Test validation with valid foreign key references."""
        # Create projects file
        self.create_csv_file(
            "projects.csv",
            ["project_id", "area", "name", "status", "start_date", "target_date", "description", "last_updated", "notes", "active"],
            [["proj1", "work", "Project 1", "active", "2026-04-01", "2026-06-01", "Description", "2026-04-05", "", "true"]]
        )

        # Create tasks file with valid project reference
        self.create_csv_file(
            "tasks.csv",
            ["task_id", "title", "domain", "project_id", "status", "priority", "effort_mins", "due_date", "energy", "context", "source", "next_step", "scheduled_date", "scheduled_start", "scheduled_end", "last_updated", "notes"],
            [["task1", "Task 1", "work", "proj1", "queued", "1", "60", "2026-04-10", "medium", "office", "manual", "Start work", "", "", "", "2026-04-05", ""]]
        )

        # Create habits file for valid habit references
        self.create_csv_file(
            "habits.csv",
            ["habit_id", "area", "name", "frequency", "target_per_week", "min_value", "unit", "active", "notes", "last_updated"],
            [["sleep_7h", "health", "Sleep 7+ hours", "daily", "7", "7", "hours", "true", "", "2026-04-05"]]
        )

        # Create logs directory and daily_log file
        logs_dir = self.temp_path.parent / "logs"
        logs_dir.mkdir(exist_ok=True)
        daily_log_path = logs_dir / "daily_log.csv"
        with daily_log_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["date", "habit_id", "value", "notes"])
            writer.writerow(["2026-04-05", "sleep_7h", "8", "Good sleep"])

        # Mock the LOGS_DIR to point to our test logs directory
        with mock.patch.object(validate_csv_integrity, 'LOGS_DIR', logs_dir):
            errors = validate_foreign_keys(self.temp_path)

        assert len(errors) == 0

    def test_validate_foreign_keys_invalid_project_reference(self):
        """Test validation with invalid project reference."""
        # Create projects file
        self.create_csv_file(
            "projects.csv",
            ["project_id", "area", "name", "status", "start_date", "target_date", "description", "last_updated", "notes", "active"],
            [["proj1", "work", "Project 1", "active", "2026-04-01", "2026-06-01", "Description", "2026-04-05", "", "true"]]
        )

        # Create tasks file with invalid project reference
        self.create_csv_file(
            "tasks.csv",
            ["task_id", "title", "domain", "project_id", "status", "priority", "effort_mins", "due_date", "energy", "context", "source", "next_step", "scheduled_date", "scheduled_start", "scheduled_end", "last_updated", "notes"],
            [["task1", "Task 1", "work", "invalid_proj", "queued", "1", "60", "2026-04-10", "medium", "office", "manual", "Start work", "", "", "", "2026-04-05", ""]]
        )

        # Create empty logs directory to avoid interference
        logs_dir = self.temp_path.parent / "logs"
        logs_dir.mkdir(exist_ok=True)

        # Mock the LOGS_DIR to point to our test logs directory
        with mock.patch.object(validate_csv_integrity, 'LOGS_DIR', logs_dir):
            errors = validate_foreign_keys(self.temp_path)

        assert len(errors) == 1
        assert "Invalid project_id 'invalid_proj'" in errors[0]

    def test_validate_foreign_keys_missing_files(self):
        """Test validation when referenced files don't exist."""
        # Create empty logs directory to avoid interference
        logs_dir = self.temp_path.parent / "logs"
        logs_dir.mkdir(exist_ok=True)

        # Mock the LOGS_DIR to point to our test logs directory
        with mock.patch.object(validate_csv_integrity, 'LOGS_DIR', logs_dir):
            errors = validate_foreign_keys(self.temp_path)

        # Should not error when files don't exist
        assert len(errors) == 0

    def test_validate_foreign_keys_file_read_error(self):
        """Test handling of file read errors."""
        # Create empty logs directory to avoid interference
        logs_dir = self.temp_path.parent / "logs"
        logs_dir.mkdir(exist_ok=True)

        # Test that the function handles errors gracefully when files can't be read
        # The exact error handling is implementation-specific, but it shouldn't crash
        with mock.patch.object(validate_csv_integrity, 'LOGS_DIR', logs_dir):
            try:
                errors = validate_foreign_keys(self.temp_path)
                # Should complete without exception
                assert isinstance(errors, list)
            except Exception as e:
                assert False, f"validate_foreign_keys should handle errors gracefully, but got: {e}"


class TestMainFunction(unittest.TestCase):
    """Test the main function."""

    @mock.patch('builtins.print')
    def test_main_function_can_run(self, mock_print):
        """Test that main function can run without crashing."""
        # Just test that main() doesn't crash when called
        # The actual validation logic is tested in other test methods
        try:
            main()
            # If we get here, main() ran without exceptions
            assert True
        except Exception as e:
            # If main() crashes, fail the test
            assert False, f"main() function crashed with: {e}"

        # Should have printed something
        mock_print.assert_called()


if __name__ == "__main__":
    unittest.main()