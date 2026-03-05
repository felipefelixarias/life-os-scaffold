# life-os — Claude Code Instructions

You are operating inside a personal life operating system. The workspace uses a numbered directory structure for organization.

## First Run

If `01-ops/life-os/config/profile.json` does NOT exist, the user hasn't set up yet. Immediately run `/setup` to walk them through the onboarding questionnaire. Do not proceed with any other command until setup is complete.

## Directory Map

- `00-inbox/` — intake, scratch, quick captures
- `01-ops/` — operational systems
  - `01-ops/life-os/` — the core engine (data, config, scripts, templates)
  - `01-ops/goals/` — goal definitions and area tracking
  - `01-ops/todo/` — ad-hoc todo lists
  - `01-ops/reviews/` — weekly/monthly review outputs
- `02-career/` — applications, interviews, resume
- `03-study/` — study notes, drills, learning materials
- `04-repos/` — independent code repositories (gitignored)
- `05-assets/` — media, documents, files
- `06-admin/` — admin, finance, legal
- `99-archive/` — completed/retired items

## Key Files

- Tasks: `01-ops/life-os/data/canonical/tasks.csv`
- Goals: `01-ops/life-os/data/canonical/goals.csv`
- Habits: `01-ops/life-os/data/canonical/habits.csv`
- Projects: `01-ops/life-os/data/canonical/projects.csv`
- Calendar: `01-ops/life-os/data/canonical/calendar_events.csv`
- Time blocks: `01-ops/life-os/data/canonical/time_blocks.csv`
- Time logs: `01-ops/life-os/data/canonical/time_logs.csv`
- Daily log: `01-ops/life-os/logs/daily_log.csv`
- Profile: `01-ops/life-os/config/profile.json`

## Behavior Rules

### Time & Scheduling
- **ALWAYS run `date` before planning or scheduling.** Never assume the time.
- Only schedule events from current time forward. Never create past events.
- Respect the user's energy curve in `config/profile.json` when placing tasks.

### Data
- CSV files are the source of truth. Read before writing.
- Generated outputs go to `01-ops/life-os/outputs/` or `01-ops/reviews/`.
- Never store secrets in tracked files.

### File Organization
- Operational data (tasks, habits, goals) → `01-ops/life-os/data/canonical/`
- Career materials (resume, applications, interview prep) → `02-career/`
- Study content (notes, drills, cheatsheets) → `03-study/`
- When creating a file, ask: "What numbered bucket does this belong to?"
- When archiving, move to `99-archive/` with a date prefix

### Planning
- When plans shift, cut from lowest priority up. Protect sleep and health.
- Don't ask the user to make decisions you can make yourself. Be opinionated, let them override.
- When replanning, only schedule from current time forward.

### Google Calendar
- If gcalcli is configured (`~/.gcalcli_oauth` exists), you can read/write Google Calendar.
- Use `01-ops/life-os/scripts/gcal.py` for API operations.
- Tag pushed events with `[life-os]` in description for cleanup.

### Communication
- Be direct and concise.
- Don't repeat information the user already knows.
- When in doubt, make a reasonable default choice. The user will correct if needed.
