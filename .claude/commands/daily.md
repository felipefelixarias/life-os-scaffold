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

Use box-drawing characters for a compact terminal dashboard. Lay out data in aligned columns so it reads like an instrument panel.

```
  ┌──────────────────────────────────────────────────────┐
  │            life-os · /daily · [Day] [Date]           │
  └──────────────────────────────────────────────────────┘

  CALENDAR                          TASKS
  HH:MM  Event name                 ■ P1 task description       today
  HH:MM  Event name                 ■ P1 task description       Wed
  HH:MM  Event name                 □ P2 task description       Thu
  ...                               □ P3 task description       Fri

  HABITS - wk NN                    GOALS
  Habit       ████████░░ X/Y        Goal name        ██████░░░░ X%
  Habit       ██████░░░░ X/Y        Goal name        ████░░░░░░ X%
  Habit       ████░░░░░░ X/Y        Goal name        ██░░░░░░░░ X%
  ...                               ...

  FOCUS WINDOWS
  HH:MM-HH:MM  ████ peak   → [suggested task/habit]
  HH:MM-HH:MM  ██░░ med    → [suggested task/habit]
  HH:MM-HH:MM  ████ peak   → [suggested task/habit]
```

Keep it scannable. No fluff. The user should be able to read this in 30 seconds and know what to do.
