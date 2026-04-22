# life-os

[![CI](https://github.com/felipefelixarias/life-os-scaffold/actions/workflows/ci.yml/badge.svg)](https://github.com/felipefelixarias/life-os-scaffold/actions/workflows/ci.yml)

Your life, version-controlled. Powered by [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

## What is this

A personal operating system scaffold that runs from your terminal. Tasks, habits, goals, calendar, and reviews live in files you can inspect and version. The repo ships CSV schemas, Claude slash-command prompts, templates, and a small Google Calendar helper so you can adapt it to your own workflow.

No app. No subscription. No database. Just files and AI.

```bash
git clone https://github.com/felipefelixarias/life-os-scaffold.git life-os
cd life-os

# Set up Python dependencies (recommended for full functionality)
# See VIRTUAL_ENV_SETUP.md for detailed instructions
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Initial setup and verification
make setup
make test
claude
```

First run usually starts with `/setup`. After that:

```
/turbo       # morning: dashboard + day plan + push to Google Calendar
/shutdown    # night: review the day, update everything, preview tomorrow
/add-task    # "buy groceries, low priority"
```

## Why git

Your life data deserves the same rigor as your code. Git gives you:

- **Full history** -- `git log` shows when you added a goal, changed a habit target, or completed a sprint
- **Any machine** -- `git clone` on a new laptop and you're running in 30 seconds
- **Branching** -- experiment with a new routine on a branch, merge it if it works
- **Backup** -- your data lives on GitHub, not in some startup's database that might shut down
- **Diffs** -- `git diff` shows exactly what changed in your task list this week

## How it works

You talk to Claude. Claude reads your files, follows the command specs in `.claude/commands/`, plans your day, tracks your habits, and writes updates back to CSVs. Google Calendar integration is optional.

**Energy curve** -- tell it when you're sharpest. Deep work gets scheduled during peaks, admin during valleys.

**Priority tiers** -- tell it what's sacred and what gets cut. When plans change, it cuts from the bottom up automatically.

**17 slash commands** -- prompt files you can inspect and customize under `.claude/commands/`.

## Verification

```bash
make test             # Run tests and validation
make lint             # Check scaffold integrity
make csv-check        # Analyze CSV data files
make export-json      # Export canonical CSVs to JSON
make export-markdown  # Export canonical CSVs to Markdown
make deps-check       # Check Python dependencies
make health           # Comprehensive health check
make refresh-examples # Refresh CSV files with example data
```

- `make test` runs repo validation plus Python unit tests
- `make lint` checks scaffold integrity, command references, relative markdown links, and trailing whitespace
- `make csv-check` analyzes CSV data files and shows statistics (useful during development)
- `make export-json` / `make export-markdown` export every canonical table to `01-ops/life-os/outputs/exports/` with schema-typed values
- `make deps-check` checks Python dependencies and security status
- `make health` runs comprehensive repository health check
- `make refresh-examples` refreshes CSV files with current example data for testing/onboarding

💡 **Having dependency issues?** See [`VIRTUAL_ENV_SETUP.md`](VIRTUAL_ENV_SETUP.md) for detailed Python environment setup instructions.

## Commands

| | |
|---|---|
| `/turbo` | Morning startup: calendar + dashboard + plan + gcal push |
| `/shutdown` | End of day: review, update files, preview tomorrow |
| `/daily` | Just the dashboard, no planning |
| `/done` | Fast habit check-in for mobile |
| `/plan-day` | Just the plan, step by step |
| `/replan` | Rebuild from now (when plans change) |
| `/add-task` | Natural language task capture |
| `/log-time` | Record time spent |
| `/gcal-create` | Create a calendar event |
| `/status` | 5-line pulse check |
| `/weekly-review` | Sunday reflection + next week priorities |
| `/sprint-plan` | Full weekly sprint with daily themes |
| `/triage` | Clean up your backlog aggressively |
| `/audit` | System health check: find rot, fix it |
| `/content` | Draft social posts from recent activity |
| `/improve` | The system improves itself |
| `/setup` | First-time onboarding (runs automatically) |

## Setting up your fork safely

Your life-os will contain personal data. Set it up right:

### Option A: Private repo (recommended)

1. Create a **private** repo on GitHub (don't fork -- forks of public repos can't be made private)
2. Clone this scaffold, change the remote:
```bash
git clone https://github.com/felipefelixarias/life-os-scaffold.git life-os
cd life-os
git remote set-url origin https://github.com/YOUR_USERNAME/life-os.git
git push -u origin main
```

### Option B: Public repo with gitignored data

Your personal data is protected by default. The `.gitignore` automatically excludes:
- `01-ops/life-os/data/canonical/*.csv` (your actual task/habit/goal data)
- `01-ops/life-os/logs/*.csv` (your time logs and daily entries)
- `01-ops/life-os/config/profile.json` (your personal configuration)

### What's also protected

The `.gitignore` also excludes:
- `.env` files and secrets
- Credential files (`*.pem`, `*.key`, `*credential*.csv`, `*client_secret*.json`)
- `04-repos/` (independent code projects)
- `06-admin/finance/` (uncomment if you use it)

### Multiple machines

Once your repo is on GitHub:
```bash
# New machine
git clone https://github.com/YOUR_USERNAME/life-os.git
cd life-os
make setup
claude
# /setup detects existing profile.json, skips onboarding. You're live.

# Daily workflow
git pull                    # start of day: sync from other machines
claude                      # /turbo, work, /shutdown
git add -A && git commit    # end of day: save state
git push                    # sync for tomorrow
```

## Requirements

- **Python 3.12+** (for Google Calendar integration)
- **Claude Code** (get it at [claude.ai/code](https://claude.ai/code))
- **gcalcli** (optional, for Google Calendar sync): `pip install gcalcli`

Python dependencies for Google Calendar features:
```bash
pip install -r requirements.txt
```

The system works without Python dependencies, but you'll miss Google Calendar integration.

## Structure

```
00-inbox/          scratch, quick captures
01-ops/life-os/    the engine: config, data CSVs, scripts, templates
01-ops/goals/      goal tracking by life area
02-career/         applications, interviews, resume
03-study/          notes, drills, learning
04-repos/          code projects (gitignored)
05-assets/         media, documents
06-admin/          finance, legal
99-archive/        done
```

Numbered so `ls` shows them in order. Rename them to fit your life.

## Data

All CSVs. All in `01-ops/life-os/data/canonical/`. All version-controlled.

```
tasks.csv          what you need to do
habits.csv         what you do regularly
goals.csv          what you're working toward
projects.csv       what groups your tasks
time_blocks.csv    your planned day
time_logs.csv      what actually happened
calendar_events.csv imported calendar data
```

## Notes

- This scaffold includes prompt definitions and file schemas. It does not ship a full standalone planner binary.
- Google Calendar support depends on `gcalcli` plus your own Google OAuth setup. See [docs/google-calendar.md](docs/google-calendar.md).

## Philosophy

Own your data. Version-control your life. Start small. Compound, don't grind.

## License

MIT
