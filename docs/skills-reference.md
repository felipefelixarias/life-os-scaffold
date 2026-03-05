# Skills Reference

Skills are slash commands you run inside Claude Code. Each one reads your data files, performs an action, and outputs a result.

## Daily Operations

### `/daily` — Morning Dashboard
**When:** Start of each day
**What it does:** Shows today's calendar, top tasks by priority, habits due, upcoming goal deadlines, and suggested focus blocks based on your energy curve.
**Reads:** profile.json, tasks.csv, habits.csv, goals.csv, daily_log.csv, Google Calendar

### `/plan-day` — Generate a Day Plan
**When:** After `/daily`, or whenever you need a structured schedule
**What it does:** Creates time-blocked plan from now until bedtime. Slots tasks and habits into available windows, respecting energy curve, screen time limits, and fixed calendar events. Optionally pushes the plan to Google Calendar.
**Reads:** profile.json, tasks.csv, habits.csv, Google Calendar
**Writes:** time_blocks.csv, Google Calendar (if approved)

### `/replan` — Replan the Rest of the Day
**When:** Plans change mid-day (meeting ran long, unexpected task, energy crash)
**What it does:** Rebuilds the schedule from current time until bedtime. Uses priority tiers to decide what stays and what gets cut. Removes stale `[life-os]` events from Google Calendar and pushes the updated plan.
**Reads:** profile.json, tasks.csv, habits.csv, Google Calendar
**Writes:** time_blocks.csv, Google Calendar (if approved)

### `/status` — Quick Snapshot
**When:** Anytime you want a 5-second pulse check
**What it does:** Shows task counts by status, habit adherence this week, active goal progress, and remaining calendar events today. Compact format, 5-10 lines max.
**Reads:** tasks.csv, habits.csv, goals.csv, daily_log.csv, Google Calendar

## Data Capture

### `/add-task` — Quick Task Capture
**When:** You think of something that needs doing
**What it does:** Parses natural language into a structured task row. Infers domain, priority, effort, and energy level from context. Appends to tasks.csv.
**Reads:** tasks.csv (to avoid duplicates)
**Writes:** tasks.csv

**Examples:**
```
/add-task Buy groceries, low priority
/add-task Review PR by Friday
/add-task Call mom this weekend
```

### `/log-time` — Log Time Spent
**When:** After completing an activity
**What it does:** Records actual time spent to time_logs.csv. If the activity matches a habit, also updates the daily log.
**Reads:** habits.csv, time_logs.csv
**Writes:** time_logs.csv, daily_log.csv

**Examples:**
```
/log-time 45 min on Marovi
/log-time 30 min workout
/log-time 2 hours interview prep
```

### `/gcal-create` — Create Calendar Event
**When:** You need to add something to your Google Calendar
**What it does:** Parses natural language into a calendar event. Resolves relative dates, uses profile timezone, creates the event via Google Calendar API.
**Requires:** gcalcli authenticated

**Examples:**
```
/gcal-create Dinner at The Morris Saturday 6pm
/gcal-create Block 2-4pm tomorrow for deep work
/gcal-create Leave for airport 3pm March 21
```

## Weekly

### `/weekly-review` — Weekly Review and Planning
**When:** Sunday (or your configured review day)
**What it does:** Calculates habit adherence for the past 7 days, lists completed/slipped/carried tasks, shows time allocation by domain, and guides you through a reflection: wins, what didn't work, next week's priorities.
**Reads:** habits.csv, tasks.csv, goals.csv, time_logs.csv, daily_log.csv, Google Calendar
**Writes:** Outputs a review document to `outputs/`

## Writing Your Own Skills

Create a `.md` file in `.claude/commands/` with this structure:

```markdown
# /skill-name — Short Description

What this skill does.

## Steps
1. ...
2. ...

## Output Format
What the user sees.

## Rules
- Constraints and edge cases.
```

See [customization.md](customization.md) for more details and skill ideas.
