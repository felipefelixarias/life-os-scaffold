# /status — Quick Status Check

Show a compact snapshot of where things stand across all domains.

## Steps

1. Run `date`.
2. Read `data/canonical/tasks.csv` — count by status (queued, in_progress, blocked, done).
3. Read `data/canonical/habits.csv` + `logs/daily_log.csv` — this week's adherence.
4. Read `data/canonical/goals.csv` — progress on active goals.
5. Fetch today's remaining calendar events.

## Output Format

Compact box. Entire thing fits in one terminal view.

```
  ┌─ status · HH:MM ──────────────────────────────────┐
  │  Tasks   ██████████████░░░░░░  12 active  3 done   │
  │  Habits  ████████░░░░░░░░░░░░  4/8 today            │
  │  Goals   ██████████████░░░░░░  2 on track  1 due    │
  │  Cal     3 events left today                        │
  │  Overdue ■■ 2 tasks past due                        │
  └─────────────────────────────────────────────────────┘
```

Keep it to 5-10 lines max. This is a glance, not a report.
