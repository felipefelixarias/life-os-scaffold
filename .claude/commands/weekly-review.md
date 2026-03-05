# /weekly-review — Sunday Weekly Review

Guided reflection and planning session. Run every Sunday (or whenever the user triggers it).

## Steps

1. Run `date` to confirm current day.
2. Read `data/canonical/habits.csv` and `logs/daily_log.csv` — calculate adherence for each habit over the past 7 days.
3. Read `data/canonical/tasks.csv` — list tasks completed this week, tasks that slipped, tasks still open.
4. Read `data/canonical/goals.csv` — check progress toward active goals.
5. Read `data/canonical/time_logs.csv` — summarize time spent per domain this week (if logged).
6. Fetch past week's Google Calendar to compare planned vs actual.

## Output Format

Full-width terminal dashboard. The weekly review should feel like opening a report.

```
  ╔══════════════════════════════════════════════════════════════════╗
  ║              life-os · weekly review · wk NN                   ║
  ╚══════════════════════════════════════════════════════════════════╝

  HABITS                        TARGET  ACTUAL  STREAK
  Workout                        7/wk   ████████████░░  6/7    12d
  Marovi                         7/wk   ██████████░░░░  5/7     5d
  Interview prep                 7/wk   ████████░░░░░░  4/7     2d
  LeetCode                       5/wk   ██████░░░░░░░░  3/5     3d
  Guitar                         4/wk   ████████░░░░░░  3/4     —
  Singing                        4/wk   ████░░░░░░░░░░  1/4     —
  Drums                          3/wk   ██████░░░░░░░░  2/3     —

  TASKS                                 TIME BY DOMAIN
  ✓ Completed    12                     Career       ██████████  14h
  → Carried       3                     Marovi       ████████░░  10h
  ✗ Dropped       1                     Health       ██████░░░░   7h
  + Added         5                     Study        ████░░░░░░   5h
                                        Music        ████░░░░░░   4h

  ┌─ wins ──────────────────────────────────────────────┐
  │  (ask the user to name 1-3 wins)                    │
  └─────────────────────────────────────────────────────┘

  ┌─ what didn't work ─────────────────────────────────┐
  │  (ask the user)                                     │
  └─────────────────────────────────────────────────────┘

  NEXT WEEK PRIORITIES
  1. ...
  2. ...
  3. ...
```

## Rules

- Be honest about gaps — don't sugarcoat.
- Celebrate wins briefly, then move on.
- Suggest concrete next-week priorities based on data, not aspirations.
- If a habit has been at 0% for 2+ weeks, ask: keep, modify, or drop?
