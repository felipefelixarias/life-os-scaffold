# /sprint-plan — Weekly Sprint Planning Agent

Generate a full weekly sprint plan with daily themes, task allocation, and habit scheduling.

## Steps

1. Run `date` to get current date and identify the upcoming week (Monday-Sunday).
2. Read all data files:
   - `config/profile.json` — planning prefs, energy curve, domains
   - `data/canonical/tasks.csv` — active tasks by priority and due date
   - `data/canonical/goals.csv` — active goals and progress
   - `data/canonical/habits.csv` — habit targets and frequencies
   - `data/canonical/projects.csv` — active projects
   - `logs/daily_log.csv` — last week's habit adherence (for gap analysis)
3. Fetch next week's Google Calendar for fixed commitments.
4. **Analyze capacity:**
   - Count available hours per day (total waking hours minus fixed events minus commute)
   - Identify high-energy windows per day from energy curve
   - Calculate total habit time needed (sum of all weekly targets)
   - Calculate task time needed (sum of effort_mins for priority 1-2 tasks due this week)
5. **Allocate the week:**
   - Assign tasks to specific days based on due dates, priority, and energy requirements
   - Distribute habits across the week per their frequency targets
   - Assign daily themes based on heaviest domain that day (e.g., "Deep Work Monday", "Admin Wednesday")
   - Flag if capacity < demand and suggest what to cut using priority tiers
6. **Generate the sprint document** using `templates/sprint_template.md` as the base.
7. Save to `outputs/sprint_[start_date].md`.

## Output Format

```
# Sprint: [Mon date] → [Sun date]

## Week Overview
- Available hours: X
- Committed to habits: Y hrs
- Committed to tasks: Z hrs
- Buffer: W hrs

## Daily Breakdown

### Monday — [theme]
- [ ] Task A (priority 1, 60m)
- [ ] Habit: workout (45m)
- [ ] Habit: deep work (90m)
Fixed: [calendar events]

### Tuesday — [theme]
...

## Habit Schedule
| Habit | Mon | Tue | Wed | Thu | Fri | Sat | Sun |
|-------|-----|-----|-----|-----|-----|-----|-----|
| Workout | X | | X | | X | X | |
| ...     | | | | | | | |

## Risk Flags
- [task] due Friday but only 1 available slot — start by Wednesday
- [habit] at 2/5 target last week — schedule extra session
```

## Rules

- The sprint plan should be realistic, not aspirational. If there's not enough time, say so and suggest cuts.
- Protect weekends from overflow unless the user's profile says otherwise.
- Cluster similar tasks on the same day (context switching is expensive).
- Save the output file — this is a reference document for the week.
- If the user has a weekly review day configured, place it on that day.
