# /replan — Replan the Rest of the Day

When plans change mid-day, rebuild the schedule from now until bedtime.

## Steps

1. Run `date` to get the current time.
2. Fetch remaining Google Calendar events for today.
3. Read `data/canonical/tasks.csv` — active tasks by priority.
4. Read `data/canonical/habits.csv` — habits still due today.
5. Read `config/profile.json` — energy curve, bedtime, screen time limits.
6. Calculate available windows from NOW until bedtime, excluding fixed events.
7. Rebuild the plan using priority tiers:
   - Tier 1 (non-negotiable): sleep, health essentials
   - Tier 2 (core): main project work, exercise
   - Tier 3 (growth): content, learning, music
   - Tier 4 (nice to have): extra sessions, cleanup
   - Tier 5 (cut first): extended sessions, low-priority projects
8. Fill from Tier 1 down until time runs out.
9. Present the revised plan. Push to Google Calendar if approved.

## Rules

- Never recreate events that already passed.
- Delete or update previously pushed `[life-os]` events that are no longer valid.
- If something got cut, briefly say what and why.
- Be realistic about energy — if it's 9pm, don't schedule deep work.
