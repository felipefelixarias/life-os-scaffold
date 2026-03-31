# CSV Data Validation Documentation

This document describes the data validation system for life-os CSV files, including schemas, validation rules, and integrity checks.

## Overview

The life-os system stores all data in CSV files with strict schemas to ensure data integrity and consistency. Three main validation scripts provide comprehensive data quality assurance:

- **`validate_data.py`** - Schema validation and data type checking
- **`integrity_checker.py`** - Cross-file consistency and data integrity
- **`test_data_validation.py`** - Automated test suite

## Quick Start

```bash
# Run schema validation
make validate

# Run comprehensive integrity check
make integrity-check

# Run integrity check with auto-fix
make fix-data

# Run all validation tests
make test

# Run everything
make full-check
```

## CSV File Schemas

### Core Data Files (01-ops/life-os/data/canonical/)

#### tasks.csv
**Purpose:** Individual tasks and action items

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| task_id | string | Yes | Unique task identifier |
| project_id | string_nullable | Yes | Reference to project (can be empty) |
| title | string | Yes | Task description |
| domain | string | Yes | Life area (work, personal, health, etc.) |
| status | enum | Yes | queued, active, blocked, completed, cancelled |
| priority | int:1-5 | Yes | Priority level (1=highest, 5=lowest) |
| effort_mins | int_nullable | Yes | Estimated effort in minutes |
| due_date | date_nullable | Yes | Due date (YYYY-MM-DD format) |
| energy | enum | Yes | low, medium, high |
| context | string | Yes | Where/how to do this task |
| source | string | Yes | How task was created (manual, import, etc.) |
| next_step | string_nullable | Yes | Next concrete action |
| scheduled_date | date_nullable | Yes | When scheduled (YYYY-MM-DD) |
| scheduled_start | time_nullable | Yes | Scheduled start time (HH:MM) |
| scheduled_end | time_nullable | Yes | Scheduled end time (HH:MM) |
| last_updated | date_nullable | Yes | Last modification date |
| notes | string_nullable | Yes | Additional notes |

#### goals.csv
**Purpose:** Long-term goals and objectives

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| goal_id | string | Yes | Unique goal identifier |
| area | string | Yes | Life area (health, career, learning, etc.) |
| title | string | Yes | Goal description |
| horizon | enum | Yes | week, month, quarter, year, decade |
| target_date | date_nullable | Yes | Target completion date |
| metric_name | string_nullable | Yes | What to measure |
| metric_target | float_nullable | Yes | Target value |
| metric_current | float_nullable | Yes | Current value |
| status | enum | Yes | active, paused, completed, cancelled |
| last_updated | date_nullable | Yes | Last modification date |
| notes | string_nullable | Yes | Additional notes |

#### habits.csv
**Purpose:** Recurring behaviors to track

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| habit_id | string | Yes | Unique habit identifier |
| area | string | Yes | Life area |
| name | string | Yes | Habit name |
| frequency | enum | Yes | daily, weekly, monthly |
| target_per_week | int | Yes | Target frequency per week |
| min_value | float | Yes | Minimum value to count |
| unit | string | Yes | Unit of measurement |
| active | boolean | Yes | Whether currently tracking |
| notes | string_nullable | Yes | Additional notes |
| last_updated | date_nullable | Yes | Last modification date |

#### projects.csv
**Purpose:** Project containers for tasks

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| project_id | string | Yes | Unique project identifier |
| title | string | Yes | Project name |
| domain | string | Yes | Life area |
| status | enum | Yes | active, paused, completed, cancelled |
| priority | int:1-5 | Yes | Priority level |
| start_date | date_nullable | Yes | Project start date |
| target_date | date_nullable | Yes | Target completion date |
| description | string_nullable | Yes | Project description |
| last_updated | date_nullable | Yes | Last modification date |
| notes | string_nullable | Yes | Additional notes |

#### calendar_events.csv
**Purpose:** Imported calendar events

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| event_id | string | Yes | Unique event identifier |
| calendar_name | string | Yes | Source calendar name |
| title | string | Yes | Event title |
| start | datetime | Yes | Start time (YYYY-MM-DD HH:MM) |
| end | datetime | Yes | End time (YYYY-MM-DD HH:MM) |
| all_day | boolean | Yes | Whether all-day event |
| location | string_nullable | Yes | Event location |
| description | string_nullable | Yes | Event description |
| source | string | Yes | Import source |
| last_updated | date_nullable | Yes | Last sync date |

#### time_blocks.csv
**Purpose:** Planned time blocks

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| block_id | string | Yes | Unique block identifier |
| date | date | Yes | Date of time block |
| start | time | Yes | Start time (HH:MM) |
| end | time | Yes | End time (HH:MM) |
| title | string | Yes | Block description |
| domain | string | Yes | Life area |
| task_id | string_nullable | Yes | Associated task ID |
| source | string | Yes | How block was created |
| status | enum | Yes | planned, active, completed, cancelled |
| notes | string_nullable | Yes | Additional notes |

#### time_logs.csv
**Purpose:** Actual time spent tracking

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| log_id | string | Yes | Unique log identifier |
| date | date | Yes | Date of activity |
| activity | string | Yes | What was done |
| domain | string | Yes | Life area |
| duration_mins | int | Yes | Duration in minutes |
| start_time | time_nullable | Yes | Start time if known |
| end_time | time_nullable | Yes | End time if known |
| notes | string_nullable | Yes | Additional notes |
| last_updated | date_nullable | Yes | Last modification date |

### Log Files (01-ops/life-os/logs/)

#### daily_log.csv
**Purpose:** Daily habit tracking entries

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| date | date | Yes | Date of entry (YYYY-MM-DD) |
| habit_id | string | Yes | Reference to habit |
| value | float | Yes | Measured value |
| notes | string_nullable | Yes | Additional notes |

## Data Types

### Basic Types
- **string**: Non-empty text
- **string_nullable**: Text or empty
- **int**: Integer number
- **int_nullable**: Integer or empty
- **float**: Decimal number
- **float_nullable**: Decimal or empty
- **boolean**: true/false, 1/0, yes/no

### Constrained Types
- **int:1-5**: Integer between 1 and 5 inclusive
- **enum:value1,value2**: Must be one of the specified values

### Date/Time Types
- **date**: YYYY-MM-DD format
- **date_nullable**: YYYY-MM-DD format or empty
- **time**: HH:MM format (24-hour)
- **time_nullable**: HH:MM format or empty
- **datetime**: YYYY-MM-DD HH:MM format

## Validation Rules

### Schema Validation
1. **Required Columns**: All specified columns must exist
2. **Data Types**: Each value must match its expected type
3. **Enum Values**: Must be from allowed set
4. **Date Formats**: Must be properly formatted
5. **Range Constraints**: Numeric values within bounds

### Referential Integrity
1. **Task → Project**: task.project_id must exist in projects
2. **Time Block → Task**: time_block.task_id must exist in tasks
3. **Daily Log → Habit**: daily_log.habit_id must exist in habits

### Data Consistency
1. **Unique IDs**: No duplicate IDs within files
2. **Date Logic**: Start dates before end dates
3. **Time Logic**: Start times before end times
4. **Status Logic**: Consistent status transitions

## Using the Validation System

### Command Line Usage

```bash
# Basic schema validation
python3 01-ops/life-os/scripts/validate_data.py

# Comprehensive integrity check
python3 01-ops/life-os/scripts/integrity_checker.py

# Auto-fix common issues
python3 01-ops/life-os/scripts/integrity_checker.py --fix

# Run test suite
python3 01-ops/life-os/scripts/test_data_validation.py
```

### Makefile Targets

```bash
make validate          # Schema validation
make integrity-check    # Comprehensive check
make fix-data          # Auto-fix issues
make test              # Run tests
make full-check        # Everything
make install-hooks     # Git pre-commit validation
```

### Integration with Git

Install pre-commit hooks to validate before commits:

```bash
make install-hooks
```

This prevents committing invalid data.

## Auto-Fix Capabilities

The integrity checker can automatically fix common issues:

### Date Format Normalization
- Converts MM/DD/YYYY → YYYY-MM-DD
- Converts DD/MM/YYYY → YYYY-MM-DD  
- Converts YYYY/MM/DD → YYYY-MM-DD

### Time Format Normalization
- Converts HH:MM:SS → HH:MM
- Converts 12-hour → 24-hour format

### Duplicate ID Resolution
- Appends incremental suffixes (_2, _3, etc.)
- Preserves original data

### Usage
```bash
# Safe mode - shows issues but doesn't fix
make integrity-check

# Auto-fix mode - fixes issues automatically
make fix-data
```

## Error Types and Meanings

### Errors (Must Fix)
- **Missing required columns**: Schema violation
- **Invalid data types**: Type mismatch
- **Duplicate IDs**: Breaks uniqueness
- **File read errors**: Corrupt or missing files

### Warnings (Should Fix)
- **Date format inconsistencies**: Works but not standard
- **Orphaned references**: Dangling pointers
- **Invalid enum values**: Outside allowed set
- **Extra columns**: Unexpected data

## Best Practices

### File Maintenance
1. **Regular Validation**: Run `make validate` weekly
2. **Integrity Checks**: Run `make integrity-check` monthly
3. **Backup Before Fixes**: Git commit before `make fix-data`
4. **Test Changes**: Run `make test` after modifications

### Data Entry
1. **Use Standard Formats**: YYYY-MM-DD for dates, HH:MM for times
2. **Unique IDs**: Use descriptive, unique identifiers
3. **Consistent Enums**: Stick to defined values
4. **Complete Records**: Fill required fields

### Schema Changes
1. **Update Validators**: Modify schemas in validate_data.py
2. **Update Tests**: Add test cases for new constraints
3. **Migration Scripts**: Create scripts for existing data
4. **Documentation**: Update this document

## Troubleshooting

### Common Issues

**"Invalid date format"**
- Use YYYY-MM-DD format
- Or run `make fix-data` for auto-conversion

**"Duplicate ID found"**
- Choose unique identifiers
- Or run `make fix-data` for auto-suffixing

**"Missing required column"**
- Add missing column to CSV
- Check schema in validate_data.py

**"Orphaned reference"**
- Create referenced record
- Or remove the reference

### Debug Mode
Add debug prints to validation scripts:
```python
print(f"Debug: Checking {file_path} with schema {schema}")
```

### Support
- Check existing issues in the repository
- Run tests to isolate problems: `make test`
- Use git blame to track recent changes