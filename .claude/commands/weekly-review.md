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

```
# Weekly Review — Week of [date]

## Habit Scorecard
| Habit | Target | Actual | Streak |
|-------|--------|--------|--------|
| ...   | 5/wk   | 3/wk   | 2 days |

## Tasks
- Completed: X
- Slipped: Y (list them)
- Carried forward: Z

## Time by Domain
| Domain  | Hours |
|---------|-------|
| Career  | X     |
| Project | Y     |
| Health  | Z     |

## Wins This Week
- (ask the user to name 1-3 wins)

## What Didn't Work
- (ask the user)

## Next Week Priorities
Based on open tasks, upcoming deadlines, and habit gaps:
1. ...
2. ...
3. ...
```

## Rules

- Be honest about gaps — don't sugarcoat.
- Celebrate wins briefly, then move on.
- Suggest concrete next-week priorities based on data, not aspirations.
- If a habit has been at 0% for 2+ weeks, ask: keep, modify, or drop?
