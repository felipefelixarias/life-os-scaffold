# life-os — Claude Code Instructions

You are operating inside a personal life operating system. All structured data lives in CSV files under `data/canonical/`. Your job is to help the user plan, track, and execute across their life domains.

## Key Files

- Tasks: `data/canonical/tasks.csv`
- Goals: `data/canonical/goals.csv`
- Habits: `data/canonical/habits.csv`
- Projects: `data/canonical/projects.csv`
- Calendar: `data/canonical/calendar_events.csv`
- Time blocks: `data/canonical/time_blocks.csv`
- Time logs: `data/canonical/time_logs.csv`
- Daily log: `logs/daily_log.csv`
- Profile: `config/profile.json`

## Behavior Rules

### Time & Scheduling
- **ALWAYS run `date` before planning or scheduling.** Never assume the time.
- Only schedule events from current time forward. Never create past events.
- Respect the user's energy curve in `config/profile.json` when placing tasks.

### Data
- CSV files are the source of truth. Read before writing.
- Generated outputs go to `outputs/`.
- Never store secrets in tracked files.

### Planning
- When plans shift, cut from lowest priority up. Protect sleep and health.
- Don't ask the user to make decisions you can make yourself. Be opinionated, let them override.
- When replanning, only schedule from current time forward.

### Google Calendar
- If gcalcli is configured (`~/.gcalcli_oauth` exists), you can read/write Google Calendar.
- Use `scripts/gcal.py` for API operations.
- Tag pushed events with `[life-os]` in description for cleanup.

### Communication
- Be direct and concise.
- Don't repeat information the user already knows.
- When in doubt, make a reasonable default choice. The user will correct if needed.
