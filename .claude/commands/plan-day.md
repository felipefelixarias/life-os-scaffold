# /plan-day — Generate a Day Plan

Create a time-blocked plan for the day and optionally push it to Google Calendar.

## Steps

1. Run `date` to get the current date and time.
2. Read `config/profile.json` for energy curve, bedtime, planning preferences.
3. Fetch today's Google Calendar agenda to identify fixed commitments.
4. Read `data/canonical/tasks.csv` — get active tasks sorted by priority.
5. Read `data/canonical/habits.csv` — get habits due today.
6. Identify available time windows (gaps between fixed events, from now until bedtime).
7. Allocate tasks and habits to windows, respecting:
   - Energy curve: deep work during peaks, admin during valleys
   - Max screen time blocks (from profile)
   - Break requirements between blocks
   - User preferences (workout as first activity, music as screen break, etc.)
8. Present the plan to the user for approval/edits.
9. If approved, push to Google Calendar using `scripts/gcal.py`.

## Output Format

```
# Day Plan — [Day, Month Date]

**[start] - [end]** — Activity name
**[start] - [end]** — Activity name
...
**[bedtime]** — Lights out

Want me to push this to your calendar?
```

## Rules

- Never schedule before the current time.
- Always include a buffer before events with travel.
- Respect max screen time — alternate screen/off-screen activities.
- If the day is short, fill from highest priority down.
- Ask for confirmation before pushing to Google Calendar.
