# CSV Schema Reference

This document defines the structure and purpose of all CSV files in the life-os canonical data directory.

## File Locations

**Canonical data files:** `01-ops/life-os/data/canonical/`
- habits.csv, goals.csv, tasks.csv, projects.csv, time_blocks.csv, time_logs.csv, calendar_events.csv

**Log files:** `01-ops/life-os/logs/`
- daily_log.csv, activity_log.csv

---

## habits.csv

Recurring behaviors you want to track and build.

### Schema
```csv
habit_id,area,name,frequency,target_per_week,min_value,unit,active,notes,last_updated
```

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `habit_id` | String | Yes | Unique identifier (use snake_case) |
| `area` | String | Yes | Life domain (health, work, relationships, etc.) |
| `name` | String | Yes | Human-readable habit name |
| `frequency` | Enum | Yes | "daily" or "weekly" |
| `target_per_week` | Integer | No | How many times per week to do this |
| `min_value` | Number | No | Minimum acceptable value for completion |
| `unit` | String | No | Units of measurement (hours, minutes, pages, etc.) |
| `active` | Boolean | No | "true" if tracking, "false" if paused |
| `notes` | String | No | Additional context or motivation |
| `last_updated` | Date | No | ISO format (YYYY-MM-DD) when last modified |

### Example
```csv
sleep_7h,health,Sleep 7+ hours,daily,6,7,hours,true,Core recovery habit,2026-04-01
```

---

## goals.csv

Aspirational targets with specific metrics and timeframes.

### Schema
```csv
goal_id,area,title,horizon,target_date,metric_name,metric_target,metric_current,status,last_updated,notes
```

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `goal_id` | String | Yes | Unique identifier |
| `area` | String | Yes | Life domain |
| `title` | String | Yes | Goal description |
| `horizon` | Enum | No | "quarter", "year", "month" |
| `target_date` | Date | No | ISO format target completion date |
| `metric_name` | String | No | What you're measuring |
| `metric_target` | Number | No | Target value to reach |
| `metric_current` | Number | No | Current progress value |
| `status` | Enum | No | "active", "completed", "paused", "dropped" |
| `last_updated` | Date | No | ISO format when last modified |
| `notes` | String | No | Additional context |

### Example
```csv
run_5k,health,Run a 5K,quarter,2026-06-01,distance_km,5,0,active,2026-04-01,Training for charity run
```

---

## tasks.csv

Specific actions to complete, organized by priority and context.

### Schema
```csv
task_id,project_id,title,domain,status,priority,effort_mins,due_date,energy,context,source,next_step,scheduled_date,scheduled_start,scheduled_end,last_updated,notes
```

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `task_id` | String | Yes | Unique identifier |
| `project_id` | String | No | Link to projects.csv |
| `title` | String | Yes | Task description |
| `domain` | String | No | Life area this belongs to |
| `status` | Enum | No | "queued", "in_progress", "blocked", "completed", "done", "dropped" |
| `priority` | Enum | No | "P1", "P2", "P3" (P1=highest priority) |
| `effort_mins` | Integer | No | Estimated minutes to complete |
| `due_date` | Date | No | ISO format hard deadline |
| `energy` | Enum | No | "low", "medium", "high" |
| `context` | String | No | Where/when this can be done |
| `source` | Enum | No | "manual", "auto", "imported" |
| `next_step` | String | No | Immediate next action |
| `scheduled_date` | Date | No | When scheduled to work on it |
| `scheduled_start` | Time | No | HH:MM format start time |
| `scheduled_end` | Time | No | HH:MM format end time |
| `last_updated` | Date | No | ISO format when last modified |
| `notes` | String | No | Additional context |

### Example
```csv
setup_profile,life_os_setup,Set up life-os profile,operations,queued,P1,30,,medium,computer,manual,Copy profile.example.json to profile.json,,,2026-04-01,First-time setup task
```

---

## projects.csv

Multi-task initiatives with start and end dates.

### Schema
```csv
project_id,area,name,status,start_date,target_date,description,last_updated,notes,active
```

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `project_id` | String | Yes | Unique identifier |
| `area` | String | Yes | Life domain |
| `name` | String | Yes | Project title |
| `status` | Enum | No | "planning", "active", "paused", "completed" |
| `start_date` | Date | No | ISO format project start |
| `target_date` | Date | No | ISO format target completion |
| `description` | String | No | Project overview |
| `last_updated` | Date | No | ISO format when last modified |
| `notes` | String | No | Additional context |
| `active` | Boolean | No | "true" if currently working on it |

### Example
```csv
home_gym,health,Build home gym,active,2026-03-01,2026-05-01,Set up workout space in basement,2026-04-01,Budget $2000,true
```

---

## time_blocks.csv

Scheduled time allocations for tasks and activities.

### Schema
```csv
block_id,date,start,end,title,domain,task_id,source,status,notes
```

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `block_id` | String | Yes | Unique identifier |
| `date` | Date | Yes | ISO format date |
| `start` | Time | Yes | HH:MM format start time |
| `end` | Time | Yes | HH:MM format end time |
| `title` | String | Yes | Block description |
| `domain` | String | No | Life area |
| `task_id` | String | No | Link to tasks.csv |
| `source` | Enum | No | "manual", "auto_planner", "imported" |
| `status` | Enum | No | "planned", "in_progress", "completed", "skipped" |
| `notes` | String | No | Additional context |

### Example
```csv
block_001,2026-04-01,09:00,10:30,Deep work on quarterly review,work,qtr_review_task,auto_planner,planned,High focus time
```

---

## time_logs.csv

Actual time spent tracking for analysis and reflection.

### Schema
```csv
log_id,date,activity,domain,duration_mins,start_time,end_time,notes,last_updated
```

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `log_id` | String | Yes | Unique identifier |
| `date` | Date | Yes | ISO format date |
| `activity` | String | Yes | What was done |
| `domain` | String | No | Life area |
| `duration_mins` | Integer | No | Total minutes spent |
| `start_time` | Time | No | HH:MM format when started |
| `end_time` | Time | No | HH:MM format when finished |
| `notes` | String | No | Additional context |
| `last_updated` | Date | No | ISO format (YYYY-MM-DD) when last modified |

### Example
```csv
log_001,2026-04-01,Code review session,work,75,14:30,15:45,Very productive session,2026-04-01
```

---

## calendar_events.csv

External calendar events imported for planning integration.

### Schema
```csv
event_id,date,start_time,end_time,title,location,attendees,source,calendar,notes
```

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `event_id` | String | Yes | Unique identifier |
| `date` | Date | Yes | ISO format date |
| `start_time` | Time | Yes | HH:MM format start time |
| `end_time` | Time | Yes | HH:MM format end time |
| `title` | String | Yes | Event title |
| `location` | String | No | Where the event happens |
| `attendees` | String | No | Comma-separated list |
| `source` | Enum | No | "google_calendar", "manual", "outlook" |
| `calendar` | String | No | Source calendar name |
| `notes` | String | No | Additional context |

### Example
```csv
meet_001,2026-04-01,15:00,16:00,Team standup,Conference Room A,alice@company.com,google_calendar,Work,Weekly sync meeting
```

---

## daily_log.csv

Daily habit tracking and completion records.

### Schema
```csv
date,habit_id,value,notes
```

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `date` | Date | Yes | ISO format date when habit was tracked |
| `habit_id` | String | Yes | Reference to habits.csv |
| `value` | Number | Yes | Amount completed (matches unit in habits.csv) |
| `notes` | String | No | Additional context about the habit completion |

### Example
```csv
2026-04-01,sleep_7h,8,Slept well after early bedtime
```

---

## activity_log.csv

System activity tracking for usage analysis and improvement.

### Schema
```csv
timestamp,event,details
```

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `timestamp` | DateTime | Yes | ISO format timestamp when event occurred |
| `event` | String | Yes | Type of activity (command_run, file_updated, etc.) |
| `details` | String | No | Additional context about the activity |

### Example
```csv
2026-04-01T09:30:00Z,command_run,/turbo completed successfully
```

---

## Data Types Reference

- **String**: Text field, can be empty
- **Integer**: Whole numbers (1, 2, 3...)
- **Number**: Integers or decimals (1, 1.5, 2.0...)
- **Date**: ISO format YYYY-MM-DD (2026-04-01)
- **Time**: HH:MM format (09:30, 14:15)
- **Boolean**: "true" or "false" (as strings)
- **Enum**: One of specific allowed values (see column descriptions)

---

## Validation Rules

1. **Required fields** must not be empty
2. **Dates** must be valid and in ISO format
3. **Times** must be valid 24-hour format
4. **IDs** should be unique within each file
5. **Foreign keys** (task_id, project_id) should reference existing records
6. **Enums** must match allowed values exactly

---

## Best Practices

### ID Naming
- Use snake_case: `morning_routine`, `q1_review`
- Be descriptive but concise
- Avoid spaces and special characters

### Data Entry
- Use consistent terminology across files
- Fill optional fields when valuable for planning
- Update `last_updated` when making changes
- Use consistent domain names across files

### File Maintenance
- Archive completed items to `99-archive/` periodically
- Run `make test` to validate structure
- Keep backups before major data changes
- Use consistent date/time formats throughout
