# life-os

Your life, in plain text. Powered by [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

## What is this

A personal operating system that runs from your terminal. Tasks, habits, goals, calendar, sprints -- all in CSV files you own. Claude Code is the interface. No app. No subscription. No database. Just files and AI.

```bash
git clone https://github.com/YOUR_USERNAME/life-os.git
cd life-os
claude
```

First run walks you through setup. After that:

```
/turbo       # morning: dashboard + day plan + push to Google Calendar
/shutdown    # night: review the day, update everything, preview tomorrow
/add-task    # "buy groceries, low priority"
```

## How it works

You talk to Claude. Claude reads your files, plans your day, tracks your habits, and writes everything back to CSVs. Git is your changelog. Google Calendar is optional but powerful.

**Energy curve** -- tell it when you're sharpest. Deep work gets scheduled during peaks, admin during valleys.

**Priority tiers** -- tell it what's sacred and what gets cut. When plans change, it cuts from the bottom up automatically.

**16 slash commands** -- 8 single-purpose commands + 8 autonomous agents that chain multiple steps and make decisions.

## Commands

| | |
|---|---|
| `/turbo` | Morning startup: calendar + dashboard + plan + gcal push |
| `/shutdown` | End of day: review, update files, preview tomorrow |
| `/daily` | Just the dashboard, no planning |
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

## Philosophy

Own your data. Start small. Compound, don't grind.

## License

MIT
