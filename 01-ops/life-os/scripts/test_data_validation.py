#!/usr/bin/env python3
"""
Test suite for data validation and integrity checking.

Tests both validate_data.py and integrity_checker.py functionality
with various CSV data scenarios.
"""

import tempfile
import shutil
import csv
import os
import sys
from pathlib import Path
import unittest
from datetime import datetime

# Add the scripts directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent))

from validate_data import DataValidator
from integrity_checker import IntegrityChecker

class TestDataValidation(unittest.TestCase):
    """Test cases for CSV data validation."""

    def setUp(self):
        """Set up test environment with temporary directories."""
        self.test_dir = tempfile.mkdtemp()
        self.data_dir = Path(self.test_dir) / 'data'
        self.canonical_dir = self.data_dir / 'canonical'
        self.logs_dir = self.data_dir / 'logs'

        self.canonical_dir.mkdir(parents=True)
        self.logs_dir.mkdir(parents=True)

        self.validator = DataValidator(str(self.data_dir))
        self.checker = IntegrityChecker(str(self.data_dir))

    def tearDown(self):
        """Clean up temporary directories."""
        shutil.rmtree(self.test_dir)

    def create_test_csv(self, filename: str, headers: list, rows: list, in_logs: bool = False):
        """Helper to create test CSV files."""
        target_dir = self.logs_dir if in_logs else self.canonical_dir
        file_path = target_dir / filename

        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter=',')
            writer.writerow(headers)
            for row in rows:
                writer.writerow(row)

        return file_path

    def test_valid_tasks_csv(self):
        """Test validation of a properly formatted tasks.csv."""
        headers = [
            'task_id', 'project_id', 'title', 'domain', 'status', 'priority',
            'effort_mins', 'due_date', 'energy', 'context', 'source', 'next_step',
            'scheduled_date', 'scheduled_start', 'scheduled_end', 'last_updated', 'notes'
        ]
        rows = [
            ['task_1', 'proj_1', 'Test Task', 'work', 'queued', '2', '30',
             '2026-04-01', 'medium', 'office', 'manual', 'Start working',
             '', '', '', '2026-03-31', 'Test note']
        ]

        self.create_test_csv('tasks.csv', headers, rows)
        from validate_data import SCHEMAS
        result = self.validator.validate_csv_schema(
            self.canonical_dir / 'tasks.csv',
            SCHEMAS.get('tasks.csv', {})
        )
        self.assertTrue(result, "Valid tasks.csv should pass validation")

    def test_invalid_priority_value(self):
        """Test validation catches invalid priority values."""
        headers = [
            'task_id', 'project_id', 'title', 'domain', 'status', 'priority',
            'effort_mins', 'due_date', 'energy', 'context', 'source', 'next_step',
            'scheduled_date', 'scheduled_start', 'scheduled_end', 'last_updated', 'notes'
        ]
        rows = [
            ['task_1', 'proj_1', 'Test Task', 'work', 'queued', '10',  # Invalid priority
             '30', '2026-04-01', 'medium', 'office', 'manual', 'Start working',
             '', '', '', '2026-03-31', 'Test note']
        ]

        self.create_test_csv('tasks.csv', headers, rows)
        from validate_data import SCHEMAS
        result = self.validator.validate_csv_schema(
            self.canonical_dir / 'tasks.csv',
            SCHEMAS.get('tasks.csv', {})
        )
        self.assertFalse(result, "Invalid priority should fail validation")
        self.assertTrue(any('priority' in error for error in self.validator.errors))

    def test_missing_required_columns(self):
        """Test validation catches missing required columns."""
        headers = ['task_id', 'title', 'status']  # Missing many required columns
        rows = [['task_1', 'Test Task', 'queued']]

        self.create_test_csv('tasks.csv', headers, rows)
        from validate_data import SCHEMAS
        result = self.validator.validate_csv_schema(
            self.canonical_dir / 'tasks.csv',
            SCHEMAS.get('tasks.csv', {})
        )
        self.assertFalse(result, "Missing columns should fail validation")

    def test_duplicate_task_ids(self):
        """Test detection of duplicate task IDs."""
        headers = [
            'task_id', 'project_id', 'title', 'domain', 'status', 'priority',
            'effort_mins', 'due_date', 'energy', 'context', 'source', 'next_step',
            'scheduled_date', 'scheduled_start', 'scheduled_end', 'last_updated', 'notes'
        ]
        rows = [
            ['task_1', '', 'First Task', 'work', 'queued', '1', '30',
             '', 'medium', 'office', 'manual', '', '', '', '', '', ''],
            ['task_1', '', 'Duplicate Task', 'work', 'active', '2', '60',  # Same ID
             '', 'high', 'office', 'manual', '', '', '', '', '', '']
        ]

        file_path = self.create_test_csv('tasks.csv', headers, rows)
        duplicates = self.checker.check_duplicate_ids(file_path, 'task_id')
        self.assertEqual(duplicates, ['task_1'], "Should detect duplicate task_1")

    def test_orphaned_task_reference(self):
        """Test detection of orphaned project references in tasks."""
        # Create tasks.csv with reference to non-existent project
        task_headers = [
            'task_id', 'project_id', 'title', 'domain', 'status', 'priority',
            'effort_mins', 'due_date', 'energy', 'context', 'source', 'next_step',
            'scheduled_date', 'scheduled_start', 'scheduled_end', 'last_updated', 'notes'
        ]
        task_rows = [
            ['task_1', 'nonexistent_proj', 'Test Task', 'work', 'queued', '2',
             '30', '', 'medium', 'office', 'manual', '', '', '', '', '', '']
        ]
        self.create_test_csv('tasks.csv', task_headers, task_rows)

        # Create empty projects.csv
        proj_headers = [
            'project_id', 'title', 'domain', 'status', 'priority',
            'start_date', 'target_date', 'description', 'last_updated', 'notes'
        ]
        self.create_test_csv('projects.csv', proj_headers, [])

        orphans = self.checker.check_orphaned_references()
        self.assertIn('tasks_to_projects', orphans)
        self.assertTrue(any('nonexistent_proj' in orphan for orphan in orphans['tasks_to_projects']))

    def test_date_format_normalization(self):
        """Test date format normalization."""
        test_dates = [
            ('2026-03-31', '2026-03-31'),  # Already correct
            ('03/31/2026', '2026-03-31'),  # MM/DD/YYYY
            ('31/03/2026', '2026-03-31'),  # DD/MM/YYYY
            ('2026/03/31', '2026-03-31'),  # YYYY/MM/DD
            ('invalid', None),             # Invalid format
            ('', None),                    # Empty string
        ]

        for input_date, expected in test_dates:
            result = self.checker.normalize_date_format(input_date)
            self.assertEqual(result, expected, f"Date '{input_date}' normalization failed")

    def test_time_format_normalization(self):
        """Test time format normalization."""
        test_times = [
            ('14:30', '14:30'),          # Already correct
            ('14:30:00', '14:30'),       # With seconds
            ('2:30 PM', '14:30'),        # 12-hour format
            ('2:30:45 PM', '14:30'),     # 12-hour with seconds
            ('invalid', None),           # Invalid format
            ('', None),                  # Empty string
        ]

        for input_time, expected in test_times:
            result = self.checker.normalize_time_format(input_time)
            self.assertEqual(result, expected, f"Time '{input_time}' normalization failed")

    def test_enum_validation(self):
        """Test enum value validation."""
        # Create habits.csv with invalid frequency
        headers = [
            'habit_id', 'area', 'name', 'frequency', 'target_per_week',
            'min_value', 'unit', 'active', 'notes', 'last_updated'
        ]
        rows = [
            ['habit_1', 'health', 'Exercise', 'invalid_frequency',  # Invalid enum
             '5', '30', 'minutes', 'true', '', '']
        ]
        self.create_test_csv('habits.csv', headers, rows)

        enum_issues = self.checker.validate_enum_values()
        self.assertTrue(any('frequency' in issue and 'invalid_frequency' in issue
                          for issue in enum_issues))

    def test_daily_log_habit_reference(self):
        """Test daily log to habit reference validation."""
        # Create habits.csv
        habit_headers = [
            'habit_id', 'area', 'name', 'frequency', 'target_per_week',
            'min_value', 'unit', 'active', 'notes', 'last_updated'
        ]
        habit_rows = [
            ['exercise', 'health', 'Daily Exercise', 'daily', '7',
             '30', 'minutes', 'true', '', '']
        ]
        self.create_test_csv('habits.csv', habit_headers, habit_rows)

        # Create daily_log.csv with reference to non-existent habit
        log_headers = ['date', 'habit_id', 'value', 'notes']
        log_rows = [
            ['2026-03-31', 'nonexistent_habit', '45', '']  # Bad reference
        ]
        self.create_test_csv('daily_log.csv', log_headers, log_rows, in_logs=True)

        orphans = self.checker.check_orphaned_references()
        self.assertIn('daily_log_to_habits', orphans)

    def test_comprehensive_validation(self):
        """Test full validation pipeline."""
        # Create a complete set of valid CSV files
        self.create_valid_test_data()

        # Run full validation
        result = self.validator.validate_all()
        self.assertTrue(result, "Complete valid dataset should pass validation")

        # Run integrity check
        integrity_result = self.checker.run_full_check()
        self.assertTrue(integrity_result, "Complete valid dataset should pass integrity check")

    def create_valid_test_data(self):
        """Create a complete set of valid test data."""
        # Projects
        proj_headers = [
            'project_id', 'title', 'domain', 'status', 'priority',
            'start_date', 'target_date', 'description', 'last_updated', 'notes'
        ]
        proj_rows = [
            ['proj_1', 'Test Project', 'work', 'active', '1',
             '2026-03-01', '2026-06-01', 'A test project', '2026-03-31', '']
        ]
        self.create_test_csv('projects.csv', proj_headers, proj_rows)

        # Tasks
        task_headers = [
            'task_id', 'project_id', 'title', 'domain', 'status', 'priority',
            'effort_mins', 'due_date', 'energy', 'context', 'source', 'next_step',
            'scheduled_date', 'scheduled_start', 'scheduled_end', 'last_updated', 'notes'
        ]
        task_rows = [
            ['task_1', 'proj_1', 'Test Task', 'work', 'queued', '2', '30',
             '2026-04-01', 'medium', 'office', 'manual', 'Start working',
             '', '', '', '2026-03-31', 'Test note']
        ]
        self.create_test_csv('tasks.csv', task_headers, task_rows)

        # Goals
        goal_headers = [
            'goal_id', 'area', 'title', 'horizon', 'target_date', 'metric_name',
            'metric_target', 'metric_current', 'status', 'last_updated', 'notes'
        ]
        goal_rows = [
            ['goal_1', 'health', 'Exercise Goal', 'quarter', '2026-06-01',
             'workouts', '50', '10', 'active', '2026-03-31', '']
        ]
        self.create_test_csv('goals.csv', goal_headers, goal_rows)

        # Habits
        habit_headers = [
            'habit_id', 'area', 'name', 'frequency', 'target_per_week',
            'min_value', 'unit', 'active', 'notes', 'last_updated'
        ]
        habit_rows = [
            ['exercise', 'health', 'Daily Exercise', 'daily', '7',
             '30', 'minutes', 'true', 'Core habit', '2026-03-31']
        ]
        self.create_test_csv('habits.csv', habit_headers, habit_rows)

        # Calendar events
        cal_headers = [
            'event_id', 'calendar_name', 'title', 'start', 'end',
            'all_day', 'location', 'description', 'source', 'last_updated'
        ]
        cal_rows = []
        self.create_test_csv('calendar_events.csv', cal_headers, cal_rows)

        # Time blocks
        block_headers = [
            'block_id', 'date', 'start', 'end', 'title', 'domain',
            'task_id', 'source', 'status', 'notes'
        ]
        block_rows = [
            ['block_1', '2026-03-31', '09:00', '10:00', 'Work on task',
             'work', 'task_1', 'manual', 'planned', '']
        ]
        self.create_test_csv('time_blocks.csv', block_headers, block_rows)

        # Time logs
        log_headers = [
            'log_id', 'date', 'activity', 'domain', 'duration_mins',
            'start_time', 'end_time', 'notes', 'last_updated'
        ]
        log_rows = []
        self.create_test_csv('time_logs.csv', log_headers, log_rows)

        # Daily log
        daily_headers = ['date', 'habit_id', 'value', 'notes']
        daily_rows = [
            ['2026-03-31', 'exercise', '45', 'Good workout']
        ]
        self.create_test_csv('daily_log.csv', daily_headers, daily_rows, in_logs=True)

def run_tests():
    """Run all validation tests."""
    print("🧪 Running data validation tests...")

    # Set up test discovery
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestDataValidation)

    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    if result.wasSuccessful():
        print("\n✅ All tests passed!")
        return True
    else:
        print(f"\n❌ {len(result.failures)} test(s) failed, {len(result.errors)} error(s)")
        return False

def main():
    """Main entry point for test runner."""
    success = run_tests()
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()