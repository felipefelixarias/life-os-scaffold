# /turbo — Morning Startup Agent

Run the full morning sequence in one shot: check the time, fetch the calendar, show the dashboard, generate a day plan, and push it to Google Calendar. No back-and-forth — just execute.

## Steps

1. Run `date` to get the current date, time, and day of week.
2. Read `config/profile.json` for timezone, energy curve, planning preferences, bedtime.
3. Determine if today is a weekday or weekend. Apply the correct planning template:
   - **Weekday**: respect commute times, work hours, evening-only habits
   - **Weekend**: later start, longer hobby sessions, all instruments
4. Fetch today's Google Calendar agenda via gcalcli.
5. Read all data files:
   - `data/canonical/tasks.csv` — active tasks by priority
   - `data/canonical/habits.csv` — habits due today
   - `data/canonical/goals.csv` — goals with upcoming deadlines
   - `logs/daily_log.csv` — recent habit completion data
6. Generate the dashboard (same format as `/daily`).
7. Identify available time windows from now until bedtime, excluding fixed calendar events.
8. Generate a time-blocked day plan:
   - Place tasks and habits into windows respecting energy curve
   - Alternate screen/off-screen activities (max 90 min screen blocks)
   - Fill from highest priority tier down
   - Include breaks and transitions
9. Present the combined dashboard + plan.
10. Ask once: "Push to calendar?" If yes, push all blocks via `scripts/gcal.py`.

## Output Format

```
# [Day], [Month Date] — Turbo

## Calendar (fixed)
- [time] Event
- [time] Event

## Top Tasks
1. [domain] Task (priority X, effort Ym)
2. ...

## Habits Due
- [ ] Habit (target)
- [ ] ...

## Day Plan
**HH:MM - HH:MM** — Activity
**HH:MM - HH:MM** — Activity
...
**[bedtime]** — Lights out

Push to calendar? (y/n)
```

## Rules

- This is a single-shot agent. Don't ask intermediate questions — make reasonable defaults and present the result.
- Never schedule before current time.
- If the day is already half over, acknowledge it and plan from now.
- If Google Calendar is not configured, skip calendar steps and work from CSV data only.
- Be opinionated about scheduling. The user will adjust if needed.
