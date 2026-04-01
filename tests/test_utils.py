#!/usr/bin/env python3
"""Tests for the utils module."""

import unittest
from datetime import date, datetime
from pathlib import Path
import tempfile
from unittest import mock
import sys
import os

# Add the scripts directory to the path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / "01-ops" / "life-os" / "scripts"))

from utils import (
    setup_logging, read_csv, write_csv, append_csv_row,
    validate_date_string, format_date, get_today_string,
    safe_get, log_activity, get_csv_files, backup_csv_file
)


class UtilsLoggingTests(unittest.TestCase):
    def test_setup_logging_creates_logger(self) -> None:
        logger = setup_logging("test_logger")
        self.assertIsNotNone(logger)
        self.assertEqual(logger.name, "test_logger")

    def test_setup_logging_avoids_duplicate_handlers(self) -> None:
        logger1 = setup_logging("test_logger_dup")
        handler_count = len(logger1.handlers)

        logger2 = setup_logging("test_logger_dup")
        self.assertEqual(len(logger2.handlers), handler_count)
        self.assertIs(logger1, logger2)


class UtilsCsvOperationsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_read_csv_success(self) -> None:
        csv_path = self.temp_path / "test.csv"
        csv_content = "id,name,value\n1,test,100\n2,example,200\n"
        csv_path.write_text(csv_content, encoding="utf-8")

        result = read_csv(csv_path)
        expected = [
            {"id": "1", "name": "test", "value": "100"},
            {"id": "2", "name": "example", "value": "200"}
        ]
        self.assertEqual(result, expected)

    def test_read_csv_missing_file_required(self) -> None:
        missing_path = self.temp_path / "missing.csv"
        with self.assertRaises(FileNotFoundError):
            read_csv(missing_path, required=True)

    def test_read_csv_missing_file_optional(self) -> None:
        missing_path = self.temp_path / "missing.csv"
        result = read_csv(missing_path, required=False)
        self.assertEqual(result, [])

    def test_write_csv_success(self) -> None:
        csv_path = self.temp_path / "output.csv"
        data = [
            {"id": "1", "name": "test"},
            {"id": "2", "name": "example"}
        ]

        success = write_csv(csv_path, data)
        self.assertTrue(success)
        self.assertTrue(csv_path.exists())

        # Verify content
        result = read_csv(csv_path)
        self.assertEqual(result, data)

    def test_write_csv_empty_data(self) -> None:
        csv_path = self.temp_path / "empty.csv"
        success = write_csv(csv_path, [])
        self.assertFalse(success)

    def test_append_csv_row_new_file(self) -> None:
        csv_path = self.temp_path / "append_new.csv"
        row = {"id": "1", "name": "test"}

        success = append_csv_row(csv_path, row)
        self.assertTrue(success)

        result = read_csv(csv_path)
        self.assertEqual(result, [row])

    def test_append_csv_row_existing_file(self) -> None:
        csv_path = self.temp_path / "append_existing.csv"
        initial_data = [{"id": "1", "name": "first"}]
        write_csv(csv_path, initial_data)

        new_row = {"id": "2", "name": "second"}
        success = append_csv_row(csv_path, new_row)
        self.assertTrue(success)

        result = read_csv(csv_path)
        expected = initial_data + [new_row]
        self.assertEqual(result, expected)


class UtilsDateHandlingTests(unittest.TestCase):
    def test_validate_date_string_valid(self) -> None:
        result = validate_date_string("2026-04-01")
        expected = date(2026, 4, 1)
        self.assertEqual(result, expected)

    def test_validate_date_string_invalid(self) -> None:
        result = validate_date_string("invalid-date")
        self.assertIsNone(result)

    def test_validate_date_string_empty_allowed(self) -> None:
        result = validate_date_string("", allow_empty=True)
        self.assertIsNone(result)

    def test_validate_date_string_empty_not_allowed(self) -> None:
        with mock.patch('utils.date') as mock_date:
            mock_date.today.return_value = date(2026, 4, 1)
            mock_date.side_effect = lambda *args, **kw: date(*args, **kw)

            result = validate_date_string("", allow_empty=False)
            self.assertEqual(result, date(2026, 4, 1))

    def test_format_date_from_date(self) -> None:
        d = date(2026, 4, 1)
        result = format_date(d)
        self.assertEqual(result, "2026-04-01")

    def test_format_date_from_datetime(self) -> None:
        dt = datetime(2026, 4, 1, 12, 30, 45)
        result = format_date(dt)
        self.assertEqual(result, "2026-04-01")

    def test_format_date_from_string(self) -> None:
        result = format_date("2026-04-01")
        self.assertEqual(result, "2026-04-01")

    def test_format_date_from_none(self) -> None:
        result = format_date(None)
        self.assertEqual(result, "")

    def test_format_date_invalid_string(self) -> None:
        result = format_date("invalid-date")
        self.assertEqual(result, "")

    @mock.patch('utils.date')
    def test_get_today_string(self, mock_date) -> None:
        mock_date.today.return_value = date(2026, 4, 1)
        result = get_today_string()
        self.assertEqual(result, "2026-04-01")


class UtilsHelperFunctionsTests(unittest.TestCase):
    def test_safe_get_existing_key(self) -> None:
        data = {"key": "value"}
        result = safe_get(data, "key")
        self.assertEqual(result, "value")

    def test_safe_get_missing_key(self) -> None:
        data = {"other": "value"}
        result = safe_get(data, "key", "default")
        self.assertEqual(result, "default")

    def test_safe_get_none_value(self) -> None:
        data = {"key": None}
        result = safe_get(data, "key", "default")
        self.assertEqual(result, "default")

    def test_safe_get_numeric_value(self) -> None:
        data = {"key": 123}
        result = safe_get(data, "key")
        self.assertEqual(result, "123")


class UtilsActivityLoggingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()

        # Mock the LOGS_DIR to use temporary directory
        self.logs_dir_patcher = mock.patch('utils.LOGS_DIR', Path(self.temp_dir.name))
        self.logs_dir_patcher.start()

    def tearDown(self) -> None:
        self.logs_dir_patcher.stop()
        self.temp_dir.cleanup()

    @mock.patch('utils.datetime')
    def test_log_activity_success(self, mock_datetime) -> None:
        mock_now = datetime(2026, 4, 1, 12, 0, 0)
        mock_datetime.now.return_value = mock_now

        success = log_activity("test_event", "test details")
        self.assertTrue(success)

        # Verify log was written
        log_path = Path(self.temp_dir.name) / "activity_log.csv"
        self.assertTrue(log_path.exists())

        result = read_csv(log_path)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["event"], "test_event")
        self.assertEqual(result[0]["details"], "test details")


class UtilsBackupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    @mock.patch('utils.datetime')
    def test_backup_csv_file_success(self, mock_datetime) -> None:
        mock_now = datetime(2026, 4, 1, 12, 30, 45)
        mock_datetime.now.return_value = mock_now
        mock_datetime.strftime = datetime.strftime  # Use real strftime

        # Create original file
        original_path = self.temp_path / "data.csv"
        original_content = "id,name\n1,test\n"
        original_path.write_text(original_content, encoding="utf-8")

        backup_path = backup_csv_file(original_path)
        self.assertIsNotNone(backup_path)
        self.assertTrue(backup_path.exists())
        self.assertIn("20260401_123045", backup_path.name)

        # Verify backup content matches original
        self.assertEqual(backup_path.read_text(encoding="utf-8"), original_content)

    def test_backup_csv_file_missing(self) -> None:
        missing_path = self.temp_path / "missing.csv"
        backup_path = backup_csv_file(missing_path)
        self.assertIsNone(backup_path)


if __name__ == "__main__":
    unittest.main()