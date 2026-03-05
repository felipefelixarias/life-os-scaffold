# /status — Quick Status Check

Show a compact snapshot of where things stand across all domains.

## Steps

1. Run `date`.
2. Read `data/canonical/tasks.csv` — count by status (queued, in_progress, blocked, done).
3. Read `data/canonical/habits.csv` + `logs/daily_log.csv` — this week's adherence.
4. Read `data/canonical/goals.csv` — progress on active goals.
5. Fetch today's remaining calendar events.

## Output Format

```
# Status — [date, time]

Tasks: X active (Y overdue) | Z done this week
Habits: X/Y on track | Z gaps
Goals: [brief one-liner per active goal]
Calendar: X events remaining today
```

Keep it to 5-10 lines max. This is a glance, not a report.
