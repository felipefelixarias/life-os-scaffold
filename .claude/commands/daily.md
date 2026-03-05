# /daily — Morning Dashboard

Show the user their daily operating dashboard. This is the primary entry point each morning.

## Steps

1. Run `date` to get the current date and time.
2. Read `config/profile.json` for timezone and planning preferences.
3. Fetch today's Google Calendar agenda via gcalcli (if configured): `gcalcli agenda "TODAY" "TOMORROW"`
4. Read `data/canonical/tasks.csv` — show active tasks sorted by priority, highlight any overdue.
5. Read `data/canonical/habits.csv` — check which habits are due today based on frequency and last logged date in `logs/daily_log.csv`.
6. Read `data/canonical/goals.csv` — show goals with upcoming target dates (next 30 days).

## Output Format

```
# Dashboard — [Day, Month Date, Year]

## Calendar
- [time] Event name
- [time] Event name

## Top Tasks (Priority 1-2)
1. [domain] Task title (due: date, effort: Xm)
2. ...

## Habits Due Today
- [ ] Habit name (target: X unit, streak: Y days)
- [ ] ...

## Goals Check-in
- Goal title — X% toward target (due: date)

## Suggested Focus
Based on your energy curve and open calendar windows, I'd suggest:
- [time block] → [task/habit]
- [time block] → [task/habit]
```

Keep it scannable. No fluff. The user should be able to read this in 30 seconds and know what to do.
