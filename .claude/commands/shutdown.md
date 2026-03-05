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

```
# Shutdown — [Day, Month Date]

## Planned vs Actual
| Planned | Status |
|---------|--------|
| Task A  | Done   |
| Task B  | Carried → tomorrow |
| Habit X | Logged |
| Habit Y | Missed |

## Updated
- tasks.csv: X tasks marked done, Y carried
- daily_log.csv: Z habits logged

## Tomorrow Preview
- [time] Calendar event
- Top tasks: A, B, C
- Habit gaps this week: [habit] at X/Y target

Goodnight.
```

## Rules

- Ask the user about task/habit completion in a single batch, not one at a time.
- If the user doesn't respond with details, make reasonable inferences from the calendar (if a workout block existed and wasn't cancelled, assume it happened).
- Keep the interaction to 1-2 exchanges max. This is end-of-day — be quick.
- Always update the files. Don't just report — actually write the changes.
