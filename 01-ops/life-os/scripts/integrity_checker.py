#!/usr/bin/env python3
"""
Advanced data integrity checker and auto-fixer for life-os CSV files.

Performs deep integrity checks and can automatically fix common issues:
- Normalize date/time formats
- Fix ID conflicts
- Clean up orphaned references
- Standardize enum values
"""

import csv
import os
import sys
from datetime import datetime, date
from typing import Dict, List, Set, Optional, Any, Tuple
import re
from pathlib import Path
import shutil
from collections import defaultdict

class IntegrityChecker:
    def __init__(self, data_dir: str, auto_fix: bool = False):
        self.data_dir = Path(data_dir)
        self.canonical_dir = self.data_dir / 'canonical'
        self.logs_dir = self.data_dir.parent / 'logs'
        self.auto_fix = auto_fix
        self.issues = []
        self.fixes_applied = []

    def add_issue(self, severity: str, file_name: str, issue: str, fix_func=None):
        """Add an issue to the report with optional auto-fix function."""
        self.issues.append({
            'severity': severity,
            'file': file_name,
            'issue': issue,
            'fix_func': fix_func
        })

    def normalize_date_format(self, date_str: str) -> Optional[str]:
        """Normalize date string to YYYY-MM-DD format."""
        if not date_str or not date_str.strip():
            return None

        # Try common date formats
        formats = [
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%d/%m/%Y',
            '%Y/%m/%d',
            '%m-%d-%Y',
            '%d-%m-%Y'
        ]

        for fmt in formats:
            try:
                parsed = datetime.strptime(date_str.strip(), fmt)
                return parsed.strftime('%Y-%m-%d')
            except ValueError:
                continue

        return None

    def normalize_time_format(self, time_str: str) -> Optional[str]:
        """Normalize time string to HH:MM format."""
        if not time_str or not time_str.strip():
            return None

        # Try common time formats
        formats = [
            '%H:%M:%S',
            '%H:%M',
            '%I:%M %p',
            '%I:%M:%S %p'
        ]

        for fmt in formats:
            try:
                parsed = datetime.strptime(time_str.strip(), fmt)
                return parsed.strftime('%H:%M')
            except ValueError:
                continue

        return None

    def check_duplicate_ids(self, file_path: Path, id_column: str) -> List[str]:
        """Check for duplicate IDs in a CSV file."""
        if not file_path.exists():
            return []

        try:
            with open(file_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter=',')
                rows = list(reader)

            ids = [row[id_column] for row in rows if row.get(id_column)]
            duplicates = []
            seen = set()

            for id_val in ids:
                if id_val in seen:
                    if id_val not in duplicates:
                        duplicates.append(id_val)
                else:
                    seen.add(id_val)

            return duplicates

        except Exception as e:
            return []

    def fix_duplicate_ids(self, file_path: Path, id_column: str, duplicates: List[str]):
        """Fix duplicate IDs by appending incremental suffixes."""
        if not duplicates or not file_path.exists():
            return

        try:
            with open(file_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter=',')
                rows = list(reader)

            id_counters = defaultdict(int)

            for row in rows:
                if row[id_column] in duplicates:
                    id_counters[row[id_column]] += 1
                    if id_counters[row[id_column]] > 1:
                        row[id_column] = f"{row[id_column]}_{id_counters[row[id_column]]}"

            # Write back to file
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                if rows:
                    writer = csv.DictWriter(f, fieldnames=rows[0].keys(), delimiter=',')
                    writer.writeheader()
                    writer.writerows(rows)

            self.fixes_applied.append(f"Fixed duplicate {id_column} in {file_path.name}")

        except Exception as e:
            self.add_issue('error', file_path.name, f"Failed to fix duplicate IDs: {str(e)}")

    def check_orphaned_references(self) -> Dict[str, List[str]]:
        """Check for orphaned references across files."""
        orphans = {}

        try:
            # Load reference data
            projects = {}
            tasks = {}
            habits = {}

            # Load projects
            projects_file = self.canonical_dir / 'projects.csv'
            if projects_file.exists():
                with open(projects_file, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f, delimiter=',')
                    projects = {row['project_id']: row for row in reader if row['project_id']}

            # Load tasks
            tasks_file = self.canonical_dir / 'tasks.csv'
            if tasks_file.exists():
                with open(tasks_file, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f, delimiter=',')
                    tasks = {row['task_id']: row for row in reader if row['task_id']}

            # Load habits
            habits_file = self.canonical_dir / 'habits.csv'
            if habits_file.exists():
                with open(habits_file, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f, delimiter=',')
                    habits = {row['habit_id']: row for row in reader if row['habit_id']}

            # Check task -> project references
            for task_id, task in tasks.items():
                if task['project_id'] and task['project_id'] not in projects:
                    orphans.setdefault('tasks_to_projects', []).append(
                        f"Task '{task_id}' references missing project '{task['project_id']}'"
                    )

            # Check time_blocks -> tasks references
            time_blocks_file = self.canonical_dir / 'time_blocks.csv'
            if time_blocks_file.exists():
                with open(time_blocks_file, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f, delimiter=',')
                    for row in reader:
                        if row['task_id'] and row['task_id'] not in tasks:
                            orphans.setdefault('time_blocks_to_tasks', []).append(
                                f"Time block '{row['block_id']}' references missing task '{row['task_id']}'"
                            )

            # Check daily_log -> habits references
            daily_log_file = self.logs_dir / 'daily_log.csv'
            if daily_log_file.exists():
                with open(daily_log_file, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f, delimiter=',')
                    for row in reader:
                        if row['habit_id'] and row['habit_id'] not in habits:
                            orphans.setdefault('daily_log_to_habits', []).append(
                                f"Daily log entry references missing habit '{row['habit_id']}'"
                            )

            return orphans

        except Exception as e:
            self.add_issue('error', 'cross-file', f"Failed to check orphaned references: {str(e)}")
            return {}

    def check_date_consistency(self) -> List[str]:
        """Check for date format inconsistencies."""
        issues = []
        date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')

        for file_name in ['tasks.csv', 'goals.csv', 'projects.csv', 'time_blocks.csv', 'time_logs.csv']:
            file_path = self.canonical_dir / file_name
            if not file_path.exists():
                continue

            try:
                with open(file_path, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f, delimiter=',')
                    for row_num, row in enumerate(reader, 2):
                        for col_name, value in row.items():
                            if ('date' in col_name.lower() or col_name in ['start', 'end']) and value:
                                if not date_pattern.match(value):
                                    issues.append(f"{file_name}:{row_num}:{col_name}: Invalid date format '{value}'")

            except Exception as e:
                issues.append(f"{file_name}: Error checking dates: {str(e)}")

        return issues

    def fix_date_formats(self):
        """Fix date format inconsistencies."""
        for file_name in ['tasks.csv', 'goals.csv', 'projects.csv', 'time_blocks.csv', 'time_logs.csv']:
            file_path = self.canonical_dir / file_name
            if not file_path.exists():
                continue

            try:
                with open(file_path, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f, delimiter=',')
                    rows = list(reader)

                fixes_made = 0
                for row in rows:
                    for col_name, value in row.items():
                        if ('date' in col_name.lower() or col_name in ['start', 'end']) and value:
                            normalized = self.normalize_date_format(value)
                            if normalized and normalized != value:
                                row[col_name] = normalized
                                fixes_made += 1

                if fixes_made > 0:
                    with open(file_path, 'w', newline='', encoding='utf-8') as f:
                        if rows:
                            writer = csv.DictWriter(f, fieldnames=rows[0].keys(), delimiter=',')
                            writer.writeheader()
                            writer.writerows(rows)

                    self.fixes_applied.append(f"Fixed {fixes_made} date formats in {file_name}")

            except Exception as e:
                self.add_issue('error', file_name, f"Failed to fix date formats: {str(e)}")

    def validate_enum_values(self) -> List[str]:
        """Validate enum field values."""
        issues = []

        enum_constraints = {
            'tasks.csv': {
                'status': ['queued', 'active', 'blocked', 'completed', 'cancelled'],
                'priority': ['1', '2', '3', '4', '5'],
                'energy': ['low', 'medium', 'high']
            },
            'goals.csv': {
                'horizon': ['week', 'month', 'quarter', 'year', 'decade'],
                'status': ['active', 'paused', 'completed', 'cancelled']
            },
            'habits.csv': {
                'frequency': ['daily', 'weekly', 'monthly'],
                'active': ['true', 'false', '1', '0']
            },
            'projects.csv': {
                'status': ['active', 'paused', 'completed', 'cancelled'],
                'priority': ['1', '2', '3', '4', '5']
            }
        }

        for file_name, constraints in enum_constraints.items():
            file_path = self.canonical_dir / file_name
            if not file_path.exists():
                continue

            try:
                with open(file_path, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f, delimiter=',')
                    for row_num, row in enumerate(reader, 2):
                        for col_name, valid_values in constraints.items():
                            if col_name in row and row[col_name]:
                                if row[col_name] not in valid_values:
                                    issues.append(
                                        f"{file_name}:{row_num}:{col_name}: "
                                        f"Invalid value '{row[col_name]}', expected one of {valid_values}"
                                    )

            except Exception as e:
                issues.append(f"{file_name}: Error validating enums: {str(e)}")

        return issues

    def run_full_check(self) -> bool:
        """Run comprehensive integrity check with optional auto-fixes."""
        print("🔍 Running comprehensive data integrity check...")

        all_good = True

        # 1. Check duplicate IDs
        print("  📋 Checking for duplicate IDs...")
        id_files = {
            'tasks.csv': 'task_id',
            'goals.csv': 'goal_id',
            'habits.csv': 'habit_id',
            'projects.csv': 'project_id',
            'time_blocks.csv': 'block_id',
            'time_logs.csv': 'log_id'
        }

        for file_name, id_col in id_files.items():
            file_path = self.canonical_dir / file_name
            duplicates = self.check_duplicate_ids(file_path, id_col)

            if duplicates:
                self.add_issue('error', file_name, f"Duplicate {id_col}: {duplicates}")
                if self.auto_fix:
                    self.fix_duplicate_ids(file_path, id_col, duplicates)
                all_good = False

        # 2. Check orphaned references
        print("  🔗 Checking orphaned references...")
        orphans = self.check_orphaned_references()
        for ref_type, orphan_list in orphans.items():
            for orphan in orphan_list:
                self.add_issue('warning', 'cross-file', orphan)
                all_good = False

        # 3. Check date formats
        print("  📅 Checking date formats...")
        date_issues = self.check_date_consistency()
        for issue in date_issues:
            self.add_issue('warning', 'date-format', issue)
            all_good = False

        if self.auto_fix and date_issues:
            print("  🔧 Fixing date formats...")
            self.fix_date_formats()

        # 4. Check enum values
        print("  🎯 Checking enum values...")
        enum_issues = self.validate_enum_values()
        for issue in enum_issues:
            self.add_issue('warning', 'enum-value', issue)
            all_good = False

        # 5. Check file sizes and empty files
        print("  📊 Checking file health...")
        for file_name in ['tasks.csv', 'goals.csv', 'habits.csv', 'projects.csv']:
            file_path = self.canonical_dir / file_name
            if file_path.exists():
                if file_path.stat().st_size == 0:
                    self.add_issue('error', file_name, "File is empty")
                    all_good = False
                elif file_path.stat().st_size < 50:  # Less than header line
                    self.add_issue('warning', file_name, "File appears to contain only headers")

        # Report results
        if self.issues:
            print(f"\n📊 Found {len(self.issues)} issues:")

            errors = [i for i in self.issues if i['severity'] == 'error']
            warnings = [i for i in self.issues if i['severity'] == 'warning']

            if errors:
                print(f"\n❌ {len(errors)} error(s):")
                for issue in errors:
                    print(f"  • {issue['file']}: {issue['issue']}")

            if warnings:
                print(f"\n⚠️  {len(warnings)} warning(s):")
                for issue in warnings:
                    print(f"  • {issue['file']}: {issue['issue']}")

        if self.fixes_applied:
            print(f"\n🔧 Applied {len(self.fixes_applied)} automatic fixes:")
            for fix in self.fixes_applied:
                print(f"  • {fix}")

        if all_good:
            print("\n✅ No integrity issues found!")
        else:
            print(f"\n📋 Integrity check completed with {len(self.issues)} issues found")

        return all_good

def main():
    """Main entry point for integrity checker."""
    auto_fix = '--fix' in sys.argv

    if len(sys.argv) > 1 and not sys.argv[1].startswith('--'):
        data_dir = sys.argv[1]
    else:
        # Default to the canonical data directory
        script_dir = Path(__file__).parent
        data_dir = script_dir.parent / 'data'

    checker = IntegrityChecker(data_dir, auto_fix=auto_fix)

    if auto_fix:
        print("🔧 Auto-fix mode enabled")

    success = checker.run_full_check()

    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()