# /done — Quick Habit Check-in

Optimized for phone. One prompt, one answer, done.

1. Run `date` to get today's date.
2. Read `01-ops/life-os/data/canonical/habits.csv` — get all active habits.
3. Read `01-ops/life-os/logs/daily_log.csv` — check what's already logged today.
4. Show a single prompt listing only unlogged habits:

```
What did you do today?

□ marovi  □ workout  □ guitar  □ singing
□ drums   □ brand    □ packing □ review
```

5. User replies with whatever format (e.g. "marovi workout guitar" or "1,2,3" or "all except drums").
6. Append one row per completed habit to `logs/daily_log.csv`:
   ```
   2026-03-09,marovi_build,1
   2026-03-09,workout_30m,1
   ```
7. Show a one-line confirmation:

```
✓ 3/8 logged today
```

## Rules

- No follow-up questions. One prompt, one answer.
- Accept any format: names, numbers, "all", "all except X".
- If habits were already logged today, skip them and only show remaining.
- If all habits already logged, say "All done for today ✓" and exit.
