# life-os

A personal operating system powered by [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

Track goals, habits, tasks, calendar, and sprints from your terminal. Plan your day with AI. Push time blocks to Google Calendar. Review your week. All backed by plain CSV files you own.

**This is not an app.** It's a scaffold -- a numbered directory structure, a set of CSV schemas, and Claude Code commands that turn your terminal into a life dashboard. Fork it, fill in your data, and run it.

## Setup (2 minutes)

```bash
git clone https://github.com/YOUR_USERNAME/life-os.git
cd life-os
claude
```

That's it. On first run, Claude detects you haven't set up yet and walks you through a questionnaire:

1. **Name and timezone** (auto-detected)
2. **Schedule** -- wake time, work hours, bedtime
3. **Energy curve** -- when you're sharpest, when you crash
4. **Life domains** -- what areas you want to track (career, health, hobbies, etc.)
5. **Priority tiers** -- what's sacred, what gets cut when time is short
6. **Habits** -- what you want to do regularly
7. **First tasks** -- what's on your plate right now
8. **Goals** (optional) -- what you're working toward

Your answers populate `01-ops/life-os/config/profile.json` and the CSV data files. After setup:

```
/turbo          # morning dashboard + day plan + push to Google Calendar
/add-task       # "buy groceries, low priority"
/status         # quick pulse check
```

### Google Calendar (optional)

```bash
pip install gcalcli
gcalcli list    # opens browser for OAuth
```

Once authenticated, `/turbo` and `/plan-day` can push time blocks directly to your calendar.

## Directory Structure

```
life-os/
├── 00-inbox/                      # Quick captures, scratch
├── 01-ops/                        # Operations
│   ├── life-os/                   # Core engine
│   │   ├── config/profile.json    # Your timezone, energy curve, domains
│   │   ├── data/canonical/        # Source of truth CSVs
│   │   ├── logs/                  # Daily + activity logs
│   │   ├── outputs/               # Generated plans, reports
│   │   ├── scripts/gcal.py        # Google Calendar API wrapper
│   │   └── templates/             # Sprint + daily check-in templates
│   ├── goals/areas/               # Per-domain goal tracking
│   ├── todo/                      # Ad-hoc todo lists
│   └── reviews/                   # Weekly/monthly reviews
├── 02-career/                     # Applications, interviews, resume
├── 03-study/                      # Notes, drills, learning
├── 04-repos/                      # Code projects (gitignored)
├── 05-assets/                     # Media, documents
├── 06-admin/                      # Finance, legal, admin
├── 99-archive/                    # Done / retired
├── .claude/commands/              # Slash commands & agents
└── CLAUDE.md                      # Instructions for Claude Code
```

Directories are numbered so `ls` shows them in logical order. Rename, add, or remove them to match your life.

## Commands & Agents

### Commands (single-purpose)
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

### Agents (multi-step, autonomous)
| Agent | What it does |
|-------|-------------|
| `/turbo` | Full morning startup: dashboard + plan + gcal push, one shot |
| `/shutdown` | End of day: review, update tasks/habits, preview tomorrow |
| `/triage` | Scan backlog, flag stale/overdue, suggest drops |
| `/sprint-plan` | Weekly sprint with daily themes and habit scheduling |
| `/audit` | System health check: find rot, propose cleanup |
| `/content` | Plan and draft social media posts from recent activity |
| `/improve` | Analyze usage, suggest and implement system improvements |

### Onboarding
| Command | What it does |
|---------|-------------|
| `/setup` | First-time questionnaire: builds your profile, habits, tasks, goals |

## Core Concepts

**CSV as source of truth.** All structured data lives in `01-ops/life-os/data/canonical/`. No database, no sync conflicts. Git tracks history.

**Energy curve.** Your profile includes when you're sharpest and when you crash. The planner schedules deep work during peaks.

**Priority tiers.** When the day gets shorter, the system cuts from the bottom up: Tier 5 (admin) goes first, Tier 1 (sleep, health) never gets cut.

**Google Calendar.** Optional. Once set up, Claude can read your agenda, push day plans, and clean up stale blocks.

## Philosophy

1. **Own your data.** CSVs in a git repo beat any SaaS.
2. **AI as interface, not oracle.** Claude reads your files and helps you act. You decide.
3. **Start minimal.** Tasks and habits first. Add complexity when you need it.
4. **Compound, don't grind.** A workout that's also a screen break. A content post that's also interview prep.

## License

MIT
