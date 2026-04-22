# CSV Schema Reference (auto-generated)

> **Do not edit by hand.** This file is generated from
> `01-ops/life-os/scripts/csv_schemas.py` by
> `01-ops/life-os/scripts/generate_schema_docs.py`.
>
> Regenerate after schema changes:
>
> ```bash
> make docs-schemas
> ```
>
> CI runs `make docs-schemas-check` to fail builds where the schema and this
> reference have drifted apart. For prose, examples, and best practices see
> [`csv-schemas.md`](csv-schemas.md).

This document enumerates every canonical and log CSV with its full column
contract: data type, required/nullable status, enum values, numeric ranges,
and foreign-key relationships. It is the authoritative reference for tooling
and contributors writing new validators.

## Canonical Files

Located under `01-ops/life-os/data/canonical/`. These files describe ongoing state — tasks, goals, projects, etc.

## `tasks.csv`

- **Location:** `01-ops/life-os/data/canonical/tasks.csv`
- **ID column:** `task_id`
- **Columns:** 17

| Column | Type | Required | Constraints |
|---|---|---|---|
| `task_id` | str | Yes | — |
| `project_id` | str | No (nullable) | — |
| `title` | str | Yes | — |
| `domain` | str | No (nullable) | — |
| `status` | enum | No (nullable) | one of `queued`, `in_progress`, `blocked`, `completed`, `done`, `dropped` |
| `priority` | enum | No (nullable) | one of `P1`, `P2`, `P3` |
| `effort_mins` | int | No (nullable) | range 1 to 480 |
| `due_date` | date | No (nullable) | — |
| `energy` | enum | No (nullable) | one of `low`, `medium`, `high` |
| `context` | str | No (nullable) | — |
| `source` | enum | No (nullable) | one of `manual`, `auto`, `imported` |
| `next_step` | str | No (nullable) | — |
| `scheduled_date` | date | No (nullable) | — |
| `scheduled_start` | time | No (nullable) | — |
| `scheduled_end` | time | No (nullable) | — |
| `last_updated` | date | No (nullable) | — |
| `notes` | str | No (nullable) | — |

## `habits.csv`

- **Location:** `01-ops/life-os/data/canonical/habits.csv`
- **ID column:** `habit_id`
- **Columns:** 10

| Column | Type | Required | Constraints |
|---|---|---|---|
| `habit_id` | str | Yes | — |
| `area` | str | Yes | — |
| `name` | str | Yes | — |
| `frequency` | enum | Yes | one of `daily`, `weekly` |
| `target_per_week` | int | No (nullable) | range 1 to 7 |
| `min_value` | float | No (nullable) | min 0 |
| `unit` | str | No (nullable) | — |
| `active` | bool | No (nullable) | — |
| `notes` | str | No (nullable) | — |
| `last_updated` | date | No (nullable) | — |

## `goals.csv`

- **Location:** `01-ops/life-os/data/canonical/goals.csv`
- **ID column:** `goal_id`
- **Columns:** 11

| Column | Type | Required | Constraints |
|---|---|---|---|
| `goal_id` | str | Yes | — |
| `area` | str | Yes | — |
| `title` | str | Yes | — |
| `horizon` | enum | No (nullable) | one of `quarter`, `year`, `month` |
| `target_date` | date | No (nullable) | — |
| `metric_name` | str | No (nullable) | — |
| `metric_target` | float | No (nullable) | min 0 |
| `metric_current` | float | No (nullable) | min 0 |
| `status` | enum | No (nullable) | one of `active`, `completed`, `paused`, `dropped` |
| `last_updated` | date | No (nullable) | — |
| `notes` | str | No (nullable) | — |

## `projects.csv`

- **Location:** `01-ops/life-os/data/canonical/projects.csv`
- **ID column:** `project_id`
- **Columns:** 10

| Column | Type | Required | Constraints |
|---|---|---|---|
| `project_id` | str | Yes | — |
| `area` | str | Yes | — |
| `name` | str | Yes | — |
| `status` | enum | No (nullable) | one of `planning`, `active`, `paused`, `completed` |
| `start_date` | date | No (nullable) | — |
| `target_date` | date | No (nullable) | — |
| `description` | str | No (nullable) | — |
| `last_updated` | date | No (nullable) | — |
| `notes` | str | No (nullable) | — |
| `active` | bool | No (nullable) | — |

## `calendar_events.csv`

- **Location:** `01-ops/life-os/data/canonical/calendar_events.csv`
- **ID column:** `event_id`
- **Columns:** 10

| Column | Type | Required | Constraints |
|---|---|---|---|
| `event_id` | str | Yes | — |
| `date` | date | Yes | — |
| `start_time` | time | Yes | — |
| `end_time` | time | Yes | — |
| `title` | str | Yes | — |
| `location` | str | No (nullable) | — |
| `attendees` | str | No (nullable) | — |
| `source` | enum | No (nullable) | one of `google_calendar`, `manual`, `outlook` |
| `calendar` | str | No (nullable) | — |
| `notes` | str | No (nullable) | — |

## `time_blocks.csv`

- **Location:** `01-ops/life-os/data/canonical/time_blocks.csv`
- **ID column:** `block_id`
- **Columns:** 10

| Column | Type | Required | Constraints |
|---|---|---|---|
| `block_id` | str | Yes | — |
| `date` | date | Yes | — |
| `start` | time | Yes | — |
| `end` | time | Yes | — |
| `title` | str | Yes | — |
| `domain` | str | No (nullable) | — |
| `task_id` | str | No (nullable) | — |
| `source` | enum | No (nullable) | one of `manual`, `auto_planner`, `imported` |
| `status` | enum | No (nullable) | one of `planned`, `in_progress`, `completed`, `skipped` |
| `notes` | str | No (nullable) | — |

## `time_logs.csv`

- **Location:** `01-ops/life-os/data/canonical/time_logs.csv`
- **ID column:** `log_id`
- **Columns:** 9

| Column | Type | Required | Constraints |
|---|---|---|---|
| `log_id` | str | Yes | — |
| `date` | date | Yes | — |
| `activity` | str | Yes | — |
| `domain` | str | No (nullable) | — |
| `duration_mins` | int | No (nullable) | range 1 to 1440 |
| `start_time` | time | No (nullable) | — |
| `end_time` | time | No (nullable) | — |
| `notes` | str | No (nullable) | — |
| `last_updated` | date | No (nullable) | — |

## Log Files

Located under `01-ops/life-os/logs/`. Append-only records of activity over time.

## `daily_log.csv`

- **Location:** `01-ops/life-os/logs/daily_log.csv`
- **Columns:** 4

| Column | Type | Required | Constraints |
|---|---|---|---|
| `date` | date | Yes | — |
| `habit_id` | str | Yes | — |
| `value` | str | Yes | — |
| `notes` | str | No (nullable) | — |

## `activity_log.csv`

- **Location:** `01-ops/life-os/logs/activity_log.csv`
- **Columns:** 3

| Column | Type | Required | Constraints |
|---|---|---|---|
| `timestamp` | str | Yes | — |
| `event` | str | Yes | — |
| `details` | str | No (nullable) | — |

## Foreign Keys

Relationships enforced by `validate_csv_integrity`.

| Source | Source Column | Target | Target Column |
|---|---|---|---|
| `tasks.csv` (canonical) | `project_id` | `projects.csv` | `project_id` |
| `time_blocks.csv` (canonical) | `task_id` | `tasks.csv` | `task_id` |
| `daily_log.csv` (logs) | `habit_id` | `habits.csv` | `habit_id` |

## Type Glossary

| Type | Meaning |
|---|---|
| `str` | Free-form text |
| `int` | Integer (whole number) |
| `float` | Number with optional decimal |
| `date` | ISO date `YYYY-MM-DD` |
| `time` | 24-hour clock `HH:MM` |
| `bool` | One of `true`, `false`, `1`, `0`, `yes`, `no` |
| `enum` | Restricted to the values listed in the Constraints column |
