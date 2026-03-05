# life-os

A personal operating system powered by [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

Track goals, habits, tasks, calendar, and sprints from your terminal. Plan your day with AI. Push time blocks to Google Calendar. Review your week. All backed by plain CSV files you own.

**This is not an app.** It's a scaffold — a directory structure, a set of CSV schemas, and Claude Code skills that turn your terminal into a life dashboard. Fork it, fill in your data, and run it.

## Why

Most productivity tools lock your data in someone else's database, hide it behind a GUI, and charge you monthly. This is the opposite:

- **Plain CSV files** — your data is yours, version-controlled, portable
- **Claude Code as the interface** — talk to your system in natural language
- **Google Calendar sync** — read/write events directly from your terminal
- **No app to maintain** — it's just files, scripts, and an AI that understands them

## Quickstart

```bash
# 1. Fork and clone
git clone https://github.com/YOUR_USERNAME/life-os.git
cd life-os

# 2. Configure your profile
cp config/profile.example.json config/profile.json
# Edit with your timezone, preferences, and energy curve

# 3. Set up Google Calendar (optional)
pip install gcalcli
gcalcli list  # Follow OAuth flow
# See docs/google-calendar.md for details

# 4. Start using it with Claude Code
claude
# Then: "show me my tasks" / "plan my day" / "add a habit"
```

## Directory Structure

```
life-os/
├── config/
│   ├── profile.json          # Your timezone, planning prefs, energy curve
│   └── calendar_feeds.json   # Google Calendar ICS feed URLs
├── data/
│   └── canonical/            # Source of truth CSVs
│       ├── tasks.csv
│       ├── goals.csv
│       ├── habits.csv
│       ├── projects.csv
│       ├── calendar_events.csv
│       ├── time_logs.csv
│       └── time_blocks.csv
├── logs/
│   ├── activity_log.csv      # System event log
│   └── daily_log.csv         # Daily check-in tracking
├── outputs/                  # Generated plans, reports, reviews
├── scripts/
│   └── gcal.py               # Google Calendar API wrapper
├── .claude/
│   └── commands/             # Claude Code slash commands
│       ├── daily.md          # /daily — morning dashboard
│       ├── plan-day.md       # /plan-day — generate time blocks
│       ├── replan.md         # /replan — rebuild today's plan
│       ├── turbo.md          # /turbo — full morning startup (agent)
│       ├── shutdown.md       # /shutdown — end of day wrap-up (agent)
│       ├── weekly-review.md  # /weekly-review — week reflection
│       ├── sprint-plan.md    # /sprint-plan — weekly sprint setup (agent)
│       ├── add-task.md       # /add-task — quick task capture
│       ├── log-time.md       # /log-time — log time spent
│       ├── gcal-create.md    # /gcal-create — create calendar event
│       ├── status.md         # /status — quick snapshot
│       ├── triage.md         # /triage — backlog cleanup (agent)
│       ├── audit.md          # /audit — system health check (agent)
│       ├── content.md        # /content — social media planning (agent)
│       └── improve.md        # /improve — system self-improvement (agent)
├── templates/
│   ├── sprint_template.md    # Weekly sprint planning
│   └── daily_checkin.md      # Daily check-in prompts
├── docs/
│   ├── getting-started.md    # Setup guide
│   ├── google-calendar.md    # Calendar integration guide
│   ├── skills-reference.md   # All available skills
│   └── customization.md      # How to adapt to your life
├── CLAUDE.md                 # Instructions for Claude Code
└── Makefile                  # Convenience targets
```

## Core Concepts

### CSV as Source of Truth

Every piece of structured data lives in a CSV file under `data/canonical/`. No databases, no APIs, no sync conflicts. Git tracks history. Claude Code reads and writes them directly.

### Commands & Agents

All interactions are slash commands in `.claude/commands/`. **Commands** are single-purpose tools. **Agents** are multi-step workflows that make decisions and update multiple files autonomously.

#### Commands
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

#### Agents
| Agent | What it does |
|-------|-------------|
| `/turbo` | Full morning startup: calendar + dashboard + day plan + gcal push, one shot |
| `/shutdown` | End of day: review planned vs actual, update tasks/habits, preview tomorrow |
| `/triage` | Scan backlog, flag overdue/stale tasks, suggest drops and priority changes |
| `/sprint-plan` | Generate a full weekly sprint with daily themes and habit scheduling |
| `/audit` | System health check: find stale data, dead habits, missed goals |
| `/content` | Plan and draft social media posts from recent activity |
| `/improve` | Analyze system usage, identify friction, suggest and implement improvements |

### Energy Curve

Your `profile.json` includes an energy curve — when you're sharpest, when you crash, when you recover. The planner uses this to schedule deep work during peaks and admin during valleys.

### Habit Tracking

Habits are defined in `habits.csv` with frequency targets and minimum values. The daily dashboard shows streaks and gaps. No gamification, no streaks-for-streaks-sake — just data.

### Google Calendar Integration

Optional but powerful. Once authenticated via `gcalcli`, Claude Code can:
- Read your agenda for any date range
- Create events with location and reminders
- Push a full day plan as calendar blocks
- Import events from ICS feeds

See [docs/google-calendar.md](docs/google-calendar.md) for setup.

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
- **Skills**: Write new skills for your workflow (study sessions, meal planning, workout tracking)
- **Templates**: Modify sprint and check-in templates to ask questions that matter to you

## Philosophy

1. **Own your data.** CSVs in a git repo beat any SaaS.
2. **AI as interface, not oracle.** Claude Code reads your files and helps you act on them. You make the decisions.
3. **Minimum viable structure.** Start with tasks and habits. Add complexity only when you need it.
4. **Compound, don't grind.** The system should help you double-dip — a workout that's also a screen break, a content post that's also interview prep.

## Credits

Powered by [Claude Code](https://docs.anthropic.com/en/docs/claude-code) from Anthropic.

## License

MIT
