# Commands & Agents Reference

All interactions are slash commands in Claude Code. **Commands** are single-purpose tools — they do one thing and return a result. **Agents** are multi-step workflows that read multiple data sources, make decisions, update files, and optionally interact with external services.

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
/log-time 45 min on side project
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

## Agents

Agents are autonomous workflows that chain multiple steps, make decisions, and update your data. They minimize back-and-forth — you trigger them, they execute, you approve the result.

### `/turbo` — Morning Startup Agent
**When:** Start of day (replaces running `/daily` then `/plan-day` separately)
**What it does:** Fetches calendar, generates dashboard, builds day plan, and pushes to Google Calendar — all in one shot. Detects weekday vs weekend and applies the right planning template.
**Reads:** profile.json, tasks.csv, habits.csv, goals.csv, daily_log.csv, Google Calendar
**Writes:** time_blocks.csv, Google Calendar (if approved)

### `/shutdown` — End of Day Agent
**When:** End of day, before bed
**What it does:** Reviews planned vs actual, asks what got done in a single batch, marks tasks complete/carried, logs habits, previews tomorrow. Keeps the interaction to 1-2 exchanges.
**Reads:** tasks.csv, habits.csv, daily_log.csv, Google Calendar
**Writes:** tasks.csv, daily_log.csv, activity_log.csv

### `/triage` — Task Triage Agent
**When:** Backlog feels overwhelming, or weekly during sprint planning
**What it does:** Scans all tasks for overdue, stale (untouched 2+ weeks), orphaned, and duplicate items. Suggests priority adjustments based on active goals. Proposes drops aggressively — carrying dead weight is worse than fewer commitments.
**Reads:** tasks.csv, goals.csv, projects.csv
**Writes:** tasks.csv (after approval)

### `/sprint-plan` — Weekly Sprint Planning Agent
**When:** Sunday/Monday, to set up the week
**What it does:** Reads goals, tasks, habits, and next week's calendar. Calculates capacity, allocates tasks to specific days, distributes habits by frequency, assigns daily themes. Flags if demand exceeds capacity and suggests cuts.
**Reads:** profile.json, tasks.csv, goals.csv, habits.csv, projects.csv, daily_log.csv, Google Calendar
**Writes:** `outputs/sprint_[date].md`

### `/audit` — System Health Check Agent
**When:** Monthly, or whenever the system feels stale
**What it does:** Checks every data file for rot: stale tasks, dead habits (0 entries in 2 weeks), missed goal deadlines, empty projects, logging gaps. Assigns a health score out of 10 and proposes cleanup.
**Reads:** All CSV files, all logs
**Writes:** Affected files (after approval)

### `/content` — Social Media Content Agent
**When:** When you want to post or plan content for the week
**What it does:** Scans recent activity (completed tasks, goal milestones, habit streaks, wins) for content opportunities. Generates 3-5 post ideas with hooks, key points, and platform recommendations. Drafts full posts on request.
**Reads:** tasks.csv, goals.csv, daily_log.csv, content_pipeline.csv (if exists)
**Writes:** content_pipeline.csv (if exists)

### `/improve` — System Self-Improvement Agent
**When:** When something feels off, or periodically to tune the system
**What it does:** Analyzes which commands are used, which data files have data, which habits are consistently missed. Identifies friction points and proposes fixes: config tweaks, new commands, schema changes. Implements approved changes directly.
**Reads:** All files
**Writes:** Any file (after approval)

## Writing Your Own

Create a `.md` file in `.claude/commands/` with this structure:

```markdown
# /command-name — Short Description

What this does.

## Steps
1. ...
2. ...

## Output Format
What the user sees.

## Rules
- Constraints and edge cases.
```

The difference between a command and an agent is scope: commands do one thing, agents chain multiple steps and make decisions. Both use the same file format.

See [customization.md](customization.md) for more details and ideas.
