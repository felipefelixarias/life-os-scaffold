# Getting Started

## Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed
- Git

## Setup

```bash
git clone https://github.com/YOUR_USERNAME/life-os.git
cd life-os
claude
```

Claude detects this is a fresh install (no `profile.json`) and runs `/setup` automatically. It asks you about:

1. Name and timezone
2. Wake/sleep schedule and work hours
3. When you're sharpest (builds your energy curve)
4. Life domains to track (career, health, hobbies, etc.)
5. Priority tiers (what's sacred vs what gets cut)
6. Habits to track
7. Current tasks
8. Goals (optional)

Everything gets written to `01-ops/life-os/config/profile.json` and the CSV files under `01-ops/life-os/data/canonical/`.

To re-run setup later: `/setup`

## Google Calendar (optional)

```bash
pip install gcalcli
gcalcli list
```

Follow the OAuth flow in your browser. Once done, `/turbo` and `/plan-day` can push time blocks to your calendar.

See [google-calendar.md](google-calendar.md) for details.

## Daily Usage

**Morning:**
```
/turbo
```
Fetches calendar, shows dashboard, builds day plan, pushes to Google Calendar. One shot.

**During the day:**
```
/add-task fix the login bug, high priority
/log-time 45 min on side project
/replan
```

**End of day:**
```
/shutdown
```
Reviews what happened vs what was planned, updates your files, previews tomorrow.

**End of week:**
```
/weekly-review
```

## All Commands

See [skills-reference.md](skills-reference.md) for the full list of 16 commands and agents.

## Tips

- **Start small.** Tasks and habits for the first week. Add goals and time logging later.
- **Don't over-track.** Dead data is worse than no data.
- **Weekly review is the keystone.** The habit that makes all other habits work.
- **Trust the tiers.** When time is short, cut from the bottom up.
