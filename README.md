# life-os

A personal operating system powered by [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

Track goals, habits, tasks, calendar, and sprints from your terminal. Plan your day with AI. Push time blocks to Google Calendar. Review your week. All backed by plain CSV files you own.

**This is not an app.** It's a scaffold -- a numbered directory structure, a set of CSV schemas, and Claude Code commands that turn your terminal into a life dashboard. Fork it, fill in your data, and run it.

## Why

Most productivity tools lock your data in someone else's database, hide it behind a GUI, and charge you monthly. This is the opposite:

- **Plain CSV files** -- your data is yours, version-controlled, portable
- **Claude Code as the interface** -- talk to your system in natural language
- **Google Calendar sync** -- read/write events directly from your terminal
- **No app to maintain** -- it's just files, scripts, and an AI that understands them

## Quickstart

```bash
# 1. Fork and clone
git clone https://github.com/YOUR_USERNAME/life-os.git
cd life-os

# 2. Run setup
make setup

# 3. Edit your profile
# Edit 01-ops/life-os/config/profile.json with your timezone, energy curve, domains

# 4. Set up Google Calendar (optional)
pip install gcalcli
gcalcli list  # Follow OAuth flow

# 5. Start using it
claude
# Then: /turbo, /add-task, /status, or just talk to it
```

## Directory Structure

```
life-os/
├── 00-inbox/                      # Quick captures, scratch, intake
├── 01-ops/                        # Operations
│   ├── life-os/                   # Core engine
│   │   ├── config/
│   │   │   ├── profile.json       # Timezone, energy curve, planning prefs
│   │   │   └── calendar_feeds.json
│   │   ├── data/canonical/        # Source of truth CSVs
│   │   │   ├── tasks.csv
│   │   │   ├── goals.csv
│   │   │   ├── habits.csv
│   │   │   ├── projects.csv
│   │   │   ├── calendar_events.csv
│   │   │   ├── time_logs.csv
│   │   │   └── time_blocks.csv
│   │   ├── logs/
│   │   │   ├── daily_log.csv
│   │   │   └── activity_log.csv
│   │   ├── outputs/               # Generated plans, reports
│   │   ├── scripts/
│   │   │   └── gcal.py            # Google Calendar API wrapper
│   │   └── templates/
│   │       ├── sprint_template.md
│   │       └── daily_checkin.md
│   ├── goals/                     # Goal definitions
│   │   └── areas/                 # Per-domain goal tracking
│   ├── todo/                      # Ad-hoc todo lists
│   └── reviews/                   # Weekly/monthly review outputs
├── 02-career/                     # Career management
│   ├── applications/              # Job applications tracker
│   ├── interviews/                # Interview prep by company
│   └── resume/                    # Resume source files
├── 03-study/                      # Learning
│   ├── notes/                     # Study notes
│   └── drills/                    # Practice problems, exercises
├── 04-repos/                      # Code projects (gitignored)
├── 05-assets/                     # Media, documents, files
├── 06-admin/                      # Admin, finance, legal
├── 99-archive/                    # Completed/retired items
├── .claude/
│   └── commands/                  # Claude Code slash commands & agents
├── docs/                          # Documentation
├── CLAUDE.md                      # Instructions for Claude Code
└── Makefile                       # Convenience targets
```

## The Numbered System

Directories are numbered for sort order and quick navigation:

| Prefix | Purpose | Examples |
|--------|---------|---------|
| `00` | Intake | Scratch notes, quick captures, unsorted files |
| `01` | Operations | Life-os engine, goals, todos, reviews |
| `02` | Career | Applications, interviews, resume, wins |
| `03` | Study | Notes, drills, cheatsheets, learning materials |
| `04` | Repos | Independent code projects (gitignored) |
| `05` | Assets | Media, documents, reference files |
| `06` | Admin | Finance, legal, insurance, housing |
| `99` | Archive | Anything completed or no longer active |

The numbering ensures `ls` always shows directories in logical order. `01-ops` comes before `02-career` because operations are the foundation everything else runs on.

## Commands & Agents

All interactions are slash commands in `.claude/commands/`. **Commands** are single-purpose tools. **Agents** are multi-step workflows that make decisions and update multiple files autonomously.

### Commands
| Command | What it does |
|---------|-------------|
| `/daily` | Morning dashboard: calendar, tasks, habits, suggested focus |
| `/plan-day` | Generate time-blocked plan, push to Google Calendar |
| `/replan` | Rebuild today's plan from current time |
| `/add-task` | Capture a task from natural language |
| `/log-time` | Log time spent on an activity |
| `/gcal-create` | Create a Google Calendar event |
| `/status` | Quick snapshot of all domains |
| `/weekly-review` | Guided weekly reflection and planning |

### Agents
| Agent | What it does |
|-------|-------------|
| `/turbo` | Full morning startup: calendar + dashboard + day plan + gcal push, one shot |
| `/shutdown` | End of day: review planned vs actual, update tasks/habits, preview tomorrow |
| `/triage` | Scan backlog, flag overdue/stale tasks, suggest drops and priority changes |
| `/sprint-plan` | Generate a full weekly sprint with daily themes and habit scheduling |
| `/audit` | System health check: find stale data, dead habits, missed goals |
| `/content` | Plan and draft social media posts from recent activity |
| `/improve` | Analyze system usage, identify friction, suggest and implement improvements |

## Core Concepts

### CSV as Source of Truth

Every piece of structured data lives in a CSV file under `01-ops/life-os/data/canonical/`. No databases, no APIs, no sync conflicts. Git tracks history. Claude Code reads and writes them directly.

### Energy Curve

Your `profile.json` includes an energy curve -- when you're sharpest, when you crash, when you recover. The planner uses this to schedule deep work during peaks and admin during valleys.

### Priority Tiers

When the day gets shorter than planned, the system cuts from the bottom up:
1. **Non-negotiable** -- sleep, health essentials, critical deadlines
2. **Core build** -- main project, exercise, deep work
3. **Growth** -- learning, content, networking
4. **Nice to have** -- extra hobbies, cleanup, journaling
5. **Cut first** -- extended sessions, low-priority admin

### Google Calendar Integration

Optional but powerful. Once authenticated via `gcalcli`, Claude Code can read your agenda, create events, push day plans, and clean up stale blocks. See [docs/google-calendar.md](docs/google-calendar.md).

## Schemas

### tasks.csv
```
task_id, project_id, title, domain, status, priority, effort_mins,
due_date, energy, context, source, next_step, scheduled_date,
scheduled_start, scheduled_end, last_updated, notes
```

### habits.csv
```
habit_id, area, name, frequency, target_per_week, min_value,
unit, active, notes, last_updated
```

### goals.csv
```
goal_id, area, title, horizon, target_date, metric_name,
metric_target, metric_current, status, last_updated, notes
```

### time_blocks.csv
```
block_id, date, start, end, title, domain, task_id,
source, status, notes
```

## Customization

This scaffold is intentionally minimal. Adapt it to your life:

- **Domains**: Edit `profile.json` to reflect your life areas (career, health, hobbies, etc.)
- **Habits**: Add/remove rows in `habits.csv`
- **Energy curve**: Tune the times and levels to match your actual rhythm
- **Commands**: Write new commands in `.claude/commands/` for your workflow
- **Numbered dirs**: Add, rename, or remove numbered directories to match your life
- **Templates**: Modify sprint and check-in templates to ask questions that matter to you

See [docs/customization.md](docs/customization.md) for details.

## Philosophy

1. **Own your data.** CSVs in a git repo beat any SaaS.
2. **AI as interface, not oracle.** Claude Code reads your files and helps you act on them. You make the decisions.
3. **Minimum viable structure.** Start with tasks and habits. Add complexity only when you need it.
4. **Compound, don't grind.** The system should help you double-dip -- a workout that's also a screen break, a content post that's also interview prep.

## License

MIT
