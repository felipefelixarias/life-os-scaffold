# /shutdown — End of Day Agent

Close out the day: review what happened, update records, and set up tomorrow.

## Steps

1. Run `date` to confirm current time.
2. Fetch today's Google Calendar events (what was planned).
3. Read `data/canonical/tasks.csv` — identify tasks that were scheduled or in_progress today.
4. Read `data/canonical/habits.csv` and `logs/daily_log.csv` — check which habits were logged today.
5. **Review the day with the user:**
   - Show planned vs actual: what was on the calendar vs what got done
   - List tasks that were in_progress — ask: done, carried, or blocked?
   - List habits due today — ask: which did you complete?
6. **Update files based on responses:**
   - Mark completed tasks as `done` in tasks.csv with today's date
   - Mark carried tasks with tomorrow's scheduled_date
   - Log completed habits to daily_log.csv
   - Append a summary row to logs/activity_log.csv
7. **Preview tomorrow:**
   - Show tomorrow's calendar events
   - List high-priority tasks due soon
   - Note any habits that are falling behind target this week
8. Output a brief day summary.

## Output Format

Use box-drawing characters. Show the day's results at a glance, then tomorrow's preview.

```
  ┌──────────────────────────────────────────────────────┐
  │          life-os · /shutdown · [Day] [Date]          │
  └──────────────────────────────────────────────────────┘

  TODAY                              RESULT
  Task A                             ✓ done
  Task B                             → carried
  Task C                             ✗ dropped
  Habit: Workout                     ✓ logged
  Habit: LeetCode                    ✗ missed

  SCORECARD
  Tasks    ████████████░░░░░░░░  3/5 done
  Habits   ██████████░░░░░░░░░░  4/6 logged

  FILES UPDATED
  tasks.csv       3 done · 1 carried · 1 dropped
  daily_log.csv   4 habits logged

  ┌─ tomorrow ─────────────────────────────────────────┐
  │  09:00  Meeting                                     │
  │  ■ P1  Finish eval framework              due tmrw  │
  │  ■ P1  Carried: PR review                 from today│
  │  ⚠ Habit gap: LeetCode 2/5 this week               │
  └─────────────────────────────────────────────────────┘

  Goodnight.
```

## Rules

- Ask the user about task/habit completion in a single batch, not one at a time.
- If the user doesn't respond with details, make reasonable inferences from the calendar (if a workout block existed and wasn't cancelled, assume it happened).
- Keep the interaction to 1-2 exchanges max. This is end-of-day — be quick.
- Always update the files. Don't just report — actually write the changes.
