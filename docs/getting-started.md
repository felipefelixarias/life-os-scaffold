# Getting Started

## Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed
- Python 3.9+ (for Google Calendar integration)
- Git

## Setup

### 1. Fork and clone

```bash
git clone https://github.com/YOUR_USERNAME/life-os.git
cd life-os
```

### 2. Run setup

```bash
make setup
```

This creates `01-ops/life-os/config/profile.json` and `01-ops/life-os/config/calendar_feeds.json` from the example templates.

### 3. Edit your profile

Open `01-ops/life-os/config/profile.json` and customize:
- Your timezone
- Wake/sleep times
- Work hours
- Energy curve (when are you sharpest?)
- Life domains and their priorities
- Priority tiers (what gets cut when time is short?)

### 4. Add your first data

```bash
claude
# Then: "/add-task Set up my life-os system"
# Or just edit the CSVs directly
```

### 5. Set up Google Calendar (optional)

See [google-calendar.md](google-calendar.md).

## Daily Usage

Start each day with:
```
claude
/turbo
```

Or step by step:
```
/daily
/plan-day
```

When plans change:
```
/replan
```

End of week:
```
/weekly-review
```

## Commands & Agents Reference

### Commands (single-purpose)

| Command | What it does |
|---------|-------------|
| `/daily` | Morning dashboard: calendar, tasks, habits |
| `/plan-day` | Generate time-blocked plan, push to Google Calendar |
| `/replan` | Rebuild today's plan from current time |
| `/weekly-review` | Guided weekly reflection and planning |
| `/add-task` | Quick task capture from natural language |
| `/log-time` | Log time spent on an activity |
| `/gcal-create` | Create a Google Calendar event |
| `/status` | Quick snapshot of all domains |

### Agents (multi-step, autonomous)

| Agent | What it does |
|-------|-------------|
| `/turbo` | Full morning startup: dashboard + plan + gcal push in one shot |
| `/shutdown` | End of day: review, update tasks/habits, preview tomorrow |
| `/triage` | Scan backlog, flag stale/overdue tasks, suggest drops |
| `/sprint-plan` | Generate weekly sprint with daily themes and habit scheduling |
| `/audit` | System health check: find rot, propose cleanup |
| `/content` | Plan and draft social media posts from recent activity |
| `/improve` | Analyze usage, identify friction, suggest system improvements |

## Tips

- **Start small.** Just use tasks and habits for the first week. Add goals, time logging, and sprints as you build the habit.
- **Don't over-track.** Only track what you'll actually review. Dead data is worse than no data.
- **Weekly review is the keystone.** If you do nothing else, do the Sunday review. It's the habit that makes all other habits work.
- **Trust the tiers.** When time is short, cut from the bottom up. Don't agonize over what to drop.
