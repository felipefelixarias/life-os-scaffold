#!/usr/bin/env python3
"""
Data validation script for life-os CSV files.

Validates schema compliance, data integrity, and cross-referential consistency
across all canonical data files.
"""

import csv
import os
import sys
from datetime import datetime
from typing import Dict, List, Set, Optional, Any
import re
from pathlib import Path

# Define schemas for each CSV file
SCHEMAS = {
    'tasks.csv': {
        'required_columns': [
            'task_id', 'project_id', 'title', 'domain', 'status', 'priority',
            'effort_mins', 'due_date', 'energy', 'context', 'source', 'next_step',
            'scheduled_date', 'scheduled_start', 'scheduled_end', 'last_updated', 'notes'
        ],
        'data_types': {
            'task_id': 'string',
            'project_id': 'string_nullable',
            'title': 'string',
            'domain': 'string',
            'status': 'enum:queued,active,blocked,completed,cancelled',
            'priority': 'int:1-5',
            'effort_mins': 'int_nullable',
            'due_date': 'date_nullable',
            'energy': 'enum:low,medium,high',
            'context': 'string',
            'source': 'string',
            'next_step': 'string_nullable',
            'scheduled_date': 'date_nullable',
            'scheduled_start': 'time_nullable',
            'scheduled_end': 'time_nullable',
            'last_updated': 'date_nullable',
            'notes': 'string_nullable'
        }
    },
    'goals.csv': {
        'required_columns': [
            'goal_id', 'area', 'title', 'horizon', 'target_date', 'metric_name',
            'metric_target', 'metric_current', 'status', 'last_updated', 'notes'
        ],
        'data_types': {
            'goal_id': 'string',
            'area': 'string',
            'title': 'string',
            'horizon': 'enum:week,month,quarter,year,decade',
            'target_date': 'date_nullable',
            'metric_name': 'string_nullable',
            'metric_target': 'float_nullable',
            'metric_current': 'float_nullable',
            'status': 'enum:active,paused,completed,cancelled',
            'last_updated': 'date_nullable',
            'notes': 'string_nullable'
        }
    },
    'habits.csv': {
        'required_columns': [
            'habit_id', 'area', 'name', 'frequency', 'target_per_week',
            'min_value', 'unit', 'active', 'notes', 'last_updated'
        ],
        'data_types': {
            'habit_id': 'string',
            'area': 'string',
            'name': 'string',
            'frequency': 'enum:daily,weekly,monthly',
            'target_per_week': 'int',
            'min_value': 'float',
            'unit': 'string',
            'active': 'boolean',
            'notes': 'string_nullable',
            'last_updated': 'date_nullable'
        }
    },
    'projects.csv': {
        'required_columns': [
            'project_id', 'title', 'domain', 'status', 'priority',
            'start_date', 'target_date', 'description', 'last_updated', 'notes'
        ],
        'data_types': {
            'project_id': 'string',
            'title': 'string',
            'domain': 'string',
            'status': 'enum:active,paused,completed,cancelled',
            'priority': 'int:1-5',
            'start_date': 'date_nullable',
            'target_date': 'date_nullable',
            'description': 'string_nullable',
            'last_updated': 'date_nullable',
            'notes': 'string_nullable'
        }
    },
    'calendar_events.csv': {
        'required_columns': [
            'event_id', 'calendar_name', 'title', 'start', 'end',
            'all_day', 'location', 'description', 'source', 'last_updated'
        ],
        'data_types': {
            'event_id': 'string',
            'calendar_name': 'string',
            'title': 'string',
            'start': 'datetime',
            'end': 'datetime',
            'all_day': 'boolean',
            'location': 'string_nullable',
            'description': 'string_nullable',
            'source': 'string',
            'last_updated': 'date_nullable'
        }
    },
    'time_blocks.csv': {
        'required_columns': [
            'block_id', 'date', 'start', 'end', 'title', 'domain',
            'task_id', 'source', 'status', 'notes'
        ],
        'data_types': {
            'block_id': 'string',
            'date': 'date',
            'start': 'time',
            'end': 'time',
            'title': 'string',
            'domain': 'string',
            'task_id': 'string_nullable',
            'source': 'string',
            'status': 'enum:planned,active,completed,cancelled',
            'notes': 'string_nullable'
        }
    },
    'time_logs.csv': {
        'required_columns': [
            'log_id', 'date', 'activity', 'domain', 'duration_mins',
            'start_time', 'end_time', 'notes', 'last_updated'
        ],
        'data_types': {
            'log_id': 'string',
            'date': 'date',
            'activity': 'string',
            'domain': 'string',
            'duration_mins': 'int',
            'start_time': 'time_nullable',
            'end_time': 'time_nullable',
            'notes': 'string_nullable',
            'last_updated': 'date_nullable'
        }
    },
    'daily_log.csv': {
        'required_columns': ['date', 'habit_id', 'value', 'notes'],
        'data_types': {
            'date': 'date',
            'habit_id': 'string',
            'value': 'float',
            'notes': 'string_nullable'
        }
    }
}

class DataValidator:
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.canonical_dir = self.data_dir / 'canonical'
        self.logs_dir = self.data_dir.parent / 'logs'
        self.errors = []
        self.warnings = []

    def validate_value(self, value: str, data_type: str) -> bool:
        """Validate a single value against its expected data type."""
        if not value and data_type.endswith('_nullable'):
            return True
        if not value and not data_type.endswith('_nullable'):
            return False

        base_type = data_type.replace('_nullable', '')

        if base_type == 'string':
            return isinstance(value, str) and len(value.strip()) > 0
        elif base_type == 'int':
            try:
                int(value)
                return True
            except ValueError:
                return False
        elif base_type.startswith('int:'):
            # Range validation like 'int:1-5'
            try:
                val = int(value)
                range_part = base_type.split(':')[1]
                min_val, max_val = map(int, range_part.split('-'))
                return min_val <= val <= max_val
            except (ValueError, IndexError):
                return False
        elif base_type == 'float':
            try:
                float(value)
                return True
            except ValueError:
                return False
        elif base_type == 'boolean':
            return value.lower() in ('true', 'false', '1', '0', 'yes', 'no')
        elif base_type == 'date':
            try:
                datetime.strptime(value, '%Y-%m-%d')
                return True
            except ValueError:
                return False
        elif base_type == 'datetime':
            try:
                # Try common datetime formats
                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M:%S']:
                    try:
                        datetime.strptime(value, fmt)
                        return True
                    except ValueError:
                        continue
                return False
            except ValueError:
                return False
        elif base_type == 'time':
            try:
                datetime.strptime(value, '%H:%M')
                return True
            except ValueError:
                return False
        elif base_type.startswith('enum:'):
            valid_values = base_type.split(':')[1].split(',')
            return value in valid_values

        return True

    def validate_csv_schema(self, file_path: Path, schema: Dict) -> bool:
        """Validate CSV file against its schema."""
        if not file_path.exists():
            self.errors.append(f"File not found: {file_path}")
            return False

        try:
            with open(file_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f, delimiter=',')  # Comma-separated
                rows = list(reader)

            if not rows:
                self.warnings.append(f"{file_path.name}: Empty file")
                return True

            headers = rows[0]

            # Check required columns
            missing_cols = set(schema['required_columns']) - set(headers)
            if missing_cols:
                self.errors.append(f"{file_path.name}: Missing columns: {missing_cols}")
                return False

            # Check for extra columns
            extra_cols = set(headers) - set(schema['required_columns'])
            if extra_cols:
                self.warnings.append(f"{file_path.name}: Extra columns: {extra_cols}")

            # Validate data types for each row
            for row_idx, row in enumerate(rows[1:], start=2):
                if len(row) != len(headers):
                    self.errors.append(f"{file_path.name}:{row_idx}: Column count mismatch")
                    continue

                for col_idx, (header, value) in enumerate(zip(headers, row)):
                    if header in schema['data_types']:
                        expected_type = schema['data_types'][header]
                        if not self.validate_value(value, expected_type):
                            self.errors.append(
                                f"{file_path.name}:{row_idx}:{header}: "
                                f"Invalid value '{value}' for type '{expected_type}'"
                            )

            return len(self.errors) == 0

        except Exception as e:
            self.errors.append(f"{file_path.name}: Error reading file: {str(e)}")
            return False

    def validate_referential_integrity(self) -> bool:
        """Check cross-file referential integrity."""
        try:
            # Load all data
            data = {}
            for filename in SCHEMAS.keys():
                file_path = self.canonical_dir / filename
                if filename == 'daily_log.csv':
                    file_path = self.logs_dir / filename

                if file_path.exists():
                    with open(file_path, 'r', newline='', encoding='utf-8') as f:
                        reader = csv.DictReader(f, delimiter=',')
                        data[filename] = list(reader)

            # Check task -> project references
            if 'tasks.csv' in data and 'projects.csv' in data:
                project_ids = {row['project_id'] for row in data['projects.csv']
                             if row['project_id']}
                for task in data['tasks.csv']:
                    if task['project_id'] and task['project_id'] not in project_ids:
                        self.errors.append(
                            f"tasks.csv: task '{task['task_id']}' references "
                            f"non-existent project '{task['project_id']}'"
                        )

            # Check time_blocks -> tasks references
            if 'time_blocks.csv' in data and 'tasks.csv' in data:
                task_ids = {row['task_id'] for row in data['tasks.csv'] if row['task_id']}
                for block in data['time_blocks.csv']:
                    if block['task_id'] and block['task_id'] not in task_ids:
                        self.errors.append(
                            f"time_blocks.csv: block '{block['block_id']}' references "
                            f"non-existent task '{block['task_id']}'"
                        )

            # Check daily_log -> habits references
            if 'daily_log.csv' in data and 'habits.csv' in data:
                habit_ids = {row['habit_id'] for row in data['habits.csv']
                           if row['habit_id']}
                for log_entry in data['daily_log.csv']:
                    if log_entry['habit_id'] and log_entry['habit_id'] not in habit_ids:
                        self.errors.append(
                            f"daily_log.csv: entry references "
                            f"non-existent habit '{log_entry['habit_id']}'"
                        )

            return len(self.errors) == 0

        except Exception as e:
            self.errors.append(f"Referential integrity check failed: {str(e)}")
            return False

    def check_data_consistency(self) -> bool:
        """Check for logical data consistency issues."""
        try:
            # Check for duplicate IDs
            for filename, schema in SCHEMAS.items():
                file_path = self.canonical_dir / filename
                if filename == 'daily_log.csv':
                    file_path = self.logs_dir / filename

                if not file_path.exists():
                    continue

                with open(file_path, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f, delimiter=',')
                    rows = list(reader)

                # Find ID columns
                id_cols = [col for col in schema['required_columns'] if col.endswith('_id')]
                for id_col in id_cols:
                    ids = [row[id_col] for row in rows if row[id_col]]
                    duplicates = set([x for x in ids if ids.count(x) > 1])
                    if duplicates:
                        self.errors.append(
                            f"{filename}: Duplicate {id_col} values: {duplicates}"
                        )

            return len(self.errors) == 0

        except Exception as e:
            self.errors.append(f"Data consistency check failed: {str(e)}")
            return False

    def validate_all(self) -> bool:
        """Run all validation checks."""
        self.errors = []
        self.warnings = []

        print("🔍 Validating CSV schemas...")
        schema_valid = True
        for filename, schema in SCHEMAS.items():
            file_path = self.canonical_dir / filename
            if filename == 'daily_log.csv':
                file_path = self.logs_dir / filename

            if not self.validate_csv_schema(file_path, schema):
                schema_valid = False

        print("🔗 Checking referential integrity...")
        ref_valid = self.validate_referential_integrity()

        print("📊 Checking data consistency...")
        consistency_valid = self.check_data_consistency()

        # Report results
        if self.errors:
            print(f"\n❌ {len(self.errors)} error(s) found:")
            for error in self.errors:
                print(f"  • {error}")

        if self.warnings:
            print(f"\n⚠️  {len(self.warnings)} warning(s):")
            for warning in self.warnings:
                print(f"  • {warning}")

        all_valid = schema_valid and ref_valid and consistency_valid

        if all_valid:
            print("\n✅ All validation checks passed!")
        else:
            print(f"\n❌ Validation failed with {len(self.errors)} errors")

        return all_valid

def main():
    """Main entry point for validation script."""
    if len(sys.argv) > 1:
        data_dir = sys.argv[1]
    else:
        # Default to the canonical data directory
        script_dir = Path(__file__).parent
        data_dir = script_dir.parent / 'data'

    validator = DataValidator(data_dir)
    success = validator.validate_all()

    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()