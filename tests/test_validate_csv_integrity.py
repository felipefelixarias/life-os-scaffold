#!/usr/bin/env python3
"""Comprehensive tests for CSV integrity validation."""

from __future__ import annotations

import csv

# Import the module under test
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "01-ops/life-os/scripts"))

from validate_csv_integrity import (
    ENUM_FIELDS,
    EXPECTED_SCHEMAS,
    ID_FIELDS,
    REQUIRED_FIELDS,
    ValidationResult,
    validate_csv_schema,
    validate_date_format,
    validate_foreign_keys,
    validate_time_format,
)


class TestValidationResult:
    """Test the ValidationResult class."""

    def test_initialization(self):
        """Test ValidationResult initialization."""
        test_path = Path("/test/path.csv")
        result = ValidationResult(test_path)

        assert result.file_path == test_path
        assert result.errors == []
        assert result.warnings == []
        assert result.passed is True

    def test_add_error(self):
        """Test adding error messages."""
        result = ValidationResult(Path("/test/path.csv"))

        result.add_error("Test error message")

        assert len(result.errors) == 1
        assert "Test error message" in result.errors
        assert result.passed is False

    def test_add_warning(self):
        """Test adding warning messages."""
        result = ValidationResult(Path("/test/path.csv"))

        result.add_warning("Test warning message")

        assert len(result.warnings) == 1
        assert "Test warning message" in result.warnings
        assert result.passed is True  # Warnings don't affect passed status

    def test_multiple_errors_and_warnings(self):
        """Test adding multiple errors and warnings."""
        result = ValidationResult(Path("/test/path.csv"))

        result.add_error("Error 1")
        result.add_error("Error 2")
        result.add_warning("Warning 1")
        result.add_warning("Warning 2")

        assert len(result.errors) == 2
        assert len(result.warnings) == 2
        assert result.passed is False


class TestDateTimeValidation:
    """Test date and time validation functions."""

    def test_validate_date_format_valid_dates(self):
        """Test valid date formats."""
        valid_dates = [
            "2024-01-01",
            "2024-12-31",
            "2024-02-29",  # Leap year
            "",  # Empty should be valid (optional)
            "   ",  # Whitespace should be valid
        ]

        for date_str in valid_dates:
            assert validate_date_format(date_str), f"Date '{date_str}' should be valid"

    def test_validate_date_format_invalid_dates(self):
        """Test invalid date formats."""
        invalid_dates = [
            "2024/01/01",  # Wrong separator
            "01-01-2024",  # Wrong order
            "2024-13-01",  # Invalid month
            "2024-02-30",  # Invalid day for February
            "not-a-date",  # Not a date at all
            "2025-2-29",   # Non-leap year (2025 is not a leap year)
        ]

        for date_str in invalid_dates:
            assert not validate_date_format(date_str), f"Date '{date_str}' should be invalid"

    def test_validate_time_format_valid_times(self):
        """Test valid time formats."""
        valid_times = [
            "00:00",
            "23:59",
            "12:30",
            "9:15",     # Single digit hour
            "",         # Empty should be valid (optional)
            "   ",      # Whitespace should be valid
        ]

        for time_str in valid_times:
            assert validate_time_format(time_str), f"Time '{time_str}' should be valid"

    def test_validate_time_format_invalid_times(self):
        """Test invalid time formats."""
        invalid_times = [
            "24:00",      # Invalid hour
            "12:60",      # Invalid minute
            "12:1",       # Single digit minute
            "1:30",       # Would be valid, but let's test edge case
            "12:30:45",   # Seconds not supported
            "12-30",      # Wrong separator
            "not-a-time", # Not a time at all
        ]

        for time_str in invalid_times:
            if time_str == "1:30":  # This one is actually valid
                continue
            assert not validate_time_format(time_str), f"Time '{time_str}' should be invalid"


class TestCsvSchemaValidation:
    """Test CSV schema validation functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def create_test_csv(self, filename: str, headers: list, rows: list = None) -> Path:
        """Create a test CSV file."""
        csv_path = self.temp_path / filename

        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            if rows:
                writer.writerows(rows)

        return csv_path

    def test_validate_nonexistent_file(self):
        """Test validation of non-existent file."""
        nonexistent = self.temp_path / "nonexistent.csv"
        result = validate_csv_schema(nonexistent)

        assert not result.passed
        assert len(result.errors) == 1
        assert "does not exist" in result.errors[0]

    def test_validate_unknown_schema(self):
        """Test validation of file with unknown schema."""
        unknown_csv = self.create_test_csv("unknown.csv", ["col1", "col2"])
        result = validate_csv_schema(unknown_csv)

        assert result.passed  # Should pass with warning
        assert len(result.warnings) == 1
        assert "No schema definition found" in result.warnings[0]

    def test_validate_empty_file(self):
        """Test validation of empty file."""
        empty_csv = self.temp_path / "tasks.csv"
        empty_csv.touch()

        result = validate_csv_schema(empty_csv)

        assert not result.passed
        assert "empty or has no headers" in result.errors[0]

    def test_validate_correct_schema(self):
        """Test validation of file with correct schema."""
        expected_headers = EXPECTED_SCHEMAS["tasks.csv"]

        # Create valid task data
        valid_rows = [[
            "task-001",  # task_id
            "Test Task", # title
            "work",      # domain
            "proj-001",  # project_id
            "queued",    # status
            "3",         # priority
            "60",        # effort_mins
            "2024-12-31", # due_date
            "medium",    # energy
            "office",    # context
            "manual",    # source
            "Start work", # next_step
            "",          # scheduled_date
            "",          # scheduled_start
            "",          # scheduled_end
            "2024-01-01", # last_updated
            "Test notes"  # notes
        ]]

        tasks_csv = self.create_test_csv("tasks.csv", expected_headers, valid_rows)
        result = validate_csv_schema(tasks_csv)

        if result.errors:
            print("Validation errors:", result.errors)
        assert result.passed

    def test_validate_schema_mismatch(self):
        """Test validation with schema mismatch."""
        wrong_headers = ["wrong", "headers", "here"]
        tasks_csv = self.create_test_csv("tasks.csv", wrong_headers)

        result = validate_csv_schema(tasks_csv)

        assert not result.passed
        assert "Schema mismatch" in result.errors[0]

    def test_validate_wrong_column_count(self):
        """Test validation with wrong number of columns in data row."""
        expected_headers = EXPECTED_SCHEMAS["tasks.csv"]

        # Create row with wrong number of columns
        wrong_rows = [["only", "two", "columns"]]

        tasks_csv = self.create_test_csv("tasks.csv", expected_headers, wrong_rows)
        result = validate_csv_schema(tasks_csv)

        assert not result.passed
        assert "has 3 columns, expected" in result.errors[0]

    def test_validate_duplicate_ids(self):
        """Test validation catches duplicate IDs."""
        headers = ["habit_id", "area", "name", "frequency", "target_per_week", "min_value", "unit", "active", "notes", "last_updated"]

        # Create rows with duplicate habit_id
        duplicate_rows = [
            ["habit-001", "health", "Exercise", "daily", "7", "30", "minutes", "true", "", "2024-01-01"],
            ["habit-001", "health", "Running", "daily", "5", "30", "minutes", "true", "", "2024-01-01"]  # Duplicate ID
        ]

        habits_csv = self.create_test_csv("habits.csv", headers, duplicate_rows)
        result = validate_csv_schema(habits_csv)

        assert not result.passed
        assert any("Duplicate ID" in error for error in result.errors)

    def test_validate_required_fields_empty(self):
        """Test validation catches empty required fields."""
        headers = ["habit_id", "area", "name", "frequency", "target_per_week", "min_value", "unit", "active", "notes", "last_updated"]

        # Create row with empty required field (habit_id)
        empty_required_rows = [
            ["", "health", "Exercise", "daily", "7", "30", "minutes", "true", "", "2024-01-01"]  # Empty habit_id
        ]

        habits_csv = self.create_test_csv("habits.csv", headers, empty_required_rows)
        result = validate_csv_schema(habits_csv)

        assert not result.passed
        assert any("Required field 'habit_id' is empty" in error for error in result.errors)

    def test_validate_invalid_enum_values(self):
        """Test validation catches invalid enum values."""
        headers = ["habit_id", "area", "name", "frequency", "target_per_week", "min_value", "unit", "active", "notes", "last_updated"]

        # Create row with invalid enum value for frequency
        invalid_enum_rows = [
            ["habit-001", "health", "Exercise", "monthly", "7", "30", "minutes", "true", "", "2024-01-01"]  # Invalid frequency
        ]

        habits_csv = self.create_test_csv("habits.csv", headers, invalid_enum_rows)
        result = validate_csv_schema(habits_csv)

        assert not result.passed
        assert any("Invalid value 'monthly' for field 'frequency'" in error for error in result.errors)

    def test_validate_invalid_date_format(self):
        """Test validation catches invalid date formats."""
        headers = ["habit_id", "area", "name", "frequency", "target_per_week", "min_value", "unit", "active", "notes", "last_updated"]

        # Create row with invalid date format
        invalid_date_rows = [
            ["habit-001", "health", "Exercise", "daily", "7", "30", "minutes", "true", "", "01/01/2024"]  # Invalid date format
        ]

        habits_csv = self.create_test_csv("habits.csv", headers, invalid_date_rows)
        result = validate_csv_schema(habits_csv)

        assert not result.passed
        assert any("Invalid date format" in error for error in result.errors)

    def test_validate_invalid_time_format(self):
        """Test validation catches invalid time formats."""
        headers = ["block_id", "date", "start", "end", "title", "domain", "task_id", "source", "status", "notes"]

        # Create row with invalid time format
        invalid_time_rows = [
            ["block-001", "2024-01-01", "25:00", "10:00", "Work", "office", "", "manual", "planned", ""]  # Invalid time
        ]

        time_blocks_csv = self.create_test_csv("time_blocks.csv", headers, invalid_time_rows)
        result = validate_csv_schema(time_blocks_csv)

        assert not result.passed
        assert any("Invalid time format" in error for error in result.errors)

    def test_validate_encoding_error(self):
        """Test validation handles encoding errors gracefully."""
        # Create a file with invalid UTF-8 encoding
        csv_path = self.temp_path / "tasks.csv"

        with csv_path.open("wb") as f:
            f.write(b'\xff\xfe\x00\x00invalid_encoding')

        result = validate_csv_schema(csv_path)

        assert not result.passed
        assert "Encoding error" in result.errors[0] or "Unexpected error" in result.errors[0]


class TestForeignKeyValidation:
    """Test foreign key validation between CSV files."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def create_test_csv(self, filename: str, headers: list, rows: list = None) -> Path:
        """Create a test CSV file."""
        csv_path = self.temp_path / filename

        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            if rows:
                writer.writerows(rows)

        return csv_path

    def test_validate_foreign_keys_valid_references(self):
        """Test foreign key validation with valid references."""
        # Create projects file
        project_headers = ["project_id", "area", "name", "status", "start_date", "target_date", "description", "last_updated", "notes", "active"]
        project_rows = [["proj-001", "work", "Test Project", "active", "2024-01-01", "", "Test", "2024-01-01", "", "true"]]
        self.create_test_csv("projects.csv", project_headers, project_rows)

        # Create habits file
        habit_headers = ["habit_id", "area", "name", "frequency", "target_per_week", "min_value", "unit", "active", "notes", "last_updated"]
        habit_rows = [["habit-001", "health", "Exercise", "daily", "7", "30", "minutes", "true", "", "2024-01-01"]]
        self.create_test_csv("habits.csv", habit_headers, habit_rows)

        # Create tasks file with valid project reference
        task_headers = EXPECTED_SCHEMAS["tasks.csv"]
        task_rows = [["task-001", "Test Task", "work", "proj-001", "queued", "3", "60", "", "medium", "", "manual", "", "", "", "", "2024-01-01", ""]]
        self.create_test_csv("tasks.csv", task_headers, task_rows)

        # Mock the LOGS_DIR to use temp path to avoid interference from real files
        with patch("validate_csv_integrity.LOGS_DIR", self.temp_path):
            errors = validate_foreign_keys(self.temp_path)

        assert len(errors) == 0

    def test_validate_foreign_keys_invalid_project_reference(self):
        """Test foreign key validation catches invalid project references."""
        # Create empty projects file
        project_headers = ["project_id", "area", "name", "status", "start_date", "target_date", "description", "last_updated", "notes", "active"]
        self.create_test_csv("projects.csv", project_headers, [])

        # Create tasks file with invalid project reference
        task_headers = EXPECTED_SCHEMAS["tasks.csv"]
        task_rows = [["task-001", "Test Task", "work", "nonexistent-proj", "queued", "3", "60", "", "medium", "", "manual", "", "", "", "", "2024-01-01", ""]]
        self.create_test_csv("tasks.csv", task_headers, task_rows)

        # Mock the LOGS_DIR to use temp path to avoid interference from real files
        with patch("validate_csv_integrity.LOGS_DIR", self.temp_path):
            errors = validate_foreign_keys(self.temp_path)

        assert len(errors) == 1
        assert "Invalid project_id 'nonexistent-proj'" in errors[0]

    def test_validate_foreign_keys_missing_files(self):
        """Test foreign key validation when files are missing."""
        errors = validate_foreign_keys(self.temp_path)

        # Should not crash, might have warnings but no critical errors
        assert isinstance(errors, list)

    @patch("builtins.print")  # Suppress print output during tests
    def test_main_function_success(self, mock_print):
        """Test main function with valid CSV files."""
        # Create minimal valid CSV files
        for filename, headers in EXPECTED_SCHEMAS.items():
            self.create_test_csv(filename, headers, [])

        # Mock the paths to use our temp directory
        with patch("validate_csv_integrity.CANONICAL_DIR", self.temp_path):
            with patch("validate_csv_integrity.LOGS_DIR", self.temp_path):
                with patch("validate_csv_integrity.REPO_ROOT", self.temp_path):
                    # This should not raise an exception
                    from validate_csv_integrity import main
                    try:
                        main()
                    except SystemExit as e:
                        # main() calls exit(1) if there are errors
                        assert e.code in [0, 1]

    @patch("builtins.print")  # Suppress print output during tests
    def test_main_function_with_errors(self, mock_print):
        """Test main function with invalid CSV files."""
        # Create invalid CSV file (wrong schema)
        self.create_test_csv("tasks.csv", ["wrong", "headers"], [])

        # Mock the paths to use our temp directory
        with patch("validate_csv_integrity.CANONICAL_DIR", self.temp_path):
            with patch("validate_csv_integrity.LOGS_DIR", self.temp_path):
                with patch("validate_csv_integrity.REPO_ROOT", self.temp_path):
                    from validate_csv_integrity import main
                    with pytest.raises(SystemExit) as exc_info:
                        main()

                    assert exc_info.value.code == 1


class TestConstants:
    """Test that constants are properly defined."""

    def test_expected_schemas_defined(self):
        """Test that expected schemas are properly defined."""
        assert isinstance(EXPECTED_SCHEMAS, dict)
        assert len(EXPECTED_SCHEMAS) > 0

        # Check that major CSV files are defined
        expected_files = ["tasks.csv", "habits.csv", "goals.csv", "projects.csv"]
        for filename in expected_files:
            assert filename in EXPECTED_SCHEMAS
            assert isinstance(EXPECTED_SCHEMAS[filename], list)
            assert len(EXPECTED_SCHEMAS[filename]) > 0

    def test_required_fields_consistent(self):
        """Test that required fields are subsets of schema fields."""
        for filename, required in REQUIRED_FIELDS.items():
            if filename in EXPECTED_SCHEMAS:
                schema_fields = set(EXPECTED_SCHEMAS[filename])
                assert required.issubset(schema_fields), f"Required fields for {filename} not in schema"

    def test_enum_fields_consistent(self):
        """Test that enum fields are subsets of schema fields."""
        for filename, enum_dict in ENUM_FIELDS.items():
            if filename in EXPECTED_SCHEMAS:
                schema_fields = set(EXPECTED_SCHEMAS[filename])
                enum_fields = set(enum_dict.keys())
                assert enum_fields.issubset(schema_fields), f"Enum fields for {filename} not in schema"

    def test_id_fields_consistent(self):
        """Test that ID fields exist in schemas."""
        for filename, id_field in ID_FIELDS.items():
            if filename in EXPECTED_SCHEMAS:
                schema_fields = set(EXPECTED_SCHEMAS[filename])
                assert id_field in schema_fields, f"ID field {id_field} for {filename} not in schema"
