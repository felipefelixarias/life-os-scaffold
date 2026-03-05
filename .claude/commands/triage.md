# /triage — Task Triage Agent

Autonomously scan, prioritize, and clean up the task backlog.

## Steps

1. Run `date` to get current date.
2. Read `data/canonical/tasks.csv` — load all tasks.
3. Read `data/canonical/goals.csv` — understand what the user is working toward.
4. Read `data/canonical/projects.csv` — understand active projects.
5. **Flag issues:**
   - **Overdue**: tasks with due_date before today and status != done
   - **Stale**: tasks with last_updated > 14 days ago and status = queued/in_progress
   - **Orphaned**: tasks whose project_id doesn't match any active project
   - **Duplicate**: tasks with very similar titles
   - **No due date**: priority 1-2 tasks without a due_date
6. **Suggest priority adjustments:**
   - Tasks blocking active goals should be priority 1-2
   - Tasks for deprioritized projects should be lowered or dropped
   - Quick wins (effort < 30m, priority 2+) that have been sitting for a week — suggest scheduling today
7. **Present the triage report** with proposed actions.
8. Ask the user to approve, modify, or reject the batch.
9. Apply approved changes to tasks.csv.

## Output Format

Compact triage board with clear action symbols.

```
  ┌──────────────────────────────────────────────────────┐
  │            life-os · /triage · [date]                │
  └──────────────────────────────────────────────────────┘

  OVERDUE ■■■                                    3 tasks
  ✗ Submit expense report           5d late     → reschedule
  ✗ Review ML paper                 3d late     → reschedule
  ✗ Fix login redirect              2d late     → done already?

  STALE ░░░░░                                    5 tasks
  ? Research caching layer          24d idle    → drop
  ? Update deployment docs          18d idle    → drop
  ? Explore new CI pipeline         15d idle    → keep?

  QUICK WINS ⚡                                  3 tasks
  → Update .gitignore               10m  P3     → do today
  → Reply to recruiter email        15m  P2     → do today
  → Log last week's time            20m  P3     → do today

  PRIORITY SHIFTS
  ▲ Agent memory layer              P3 → P1     blocks "Launch Marovi beta"
  ▼ Refactor auth module            P2 → drop   project deprioritized

  ─────────────────────────────────────────────────────
  25 active │ 11 flagged │ 8 proposed changes

  Apply? (y/modify/n)
```

## Rules

- Be aggressive about suggesting drops. If a task has been queued for 3+ weeks with no movement, it's probably not important.
- Group related tasks when possible (e.g., "3 tasks for Project X — all stale, drop batch?").
- After applying changes, show a brief confirmation of what was updated.
- Don't ask about tasks that are clearly fine (recently updated, on schedule, progressing).
