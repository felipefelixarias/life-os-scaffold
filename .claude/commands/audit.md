# /audit — System Health Check Agent

Find rot in the system: stale data, broken habits, missed goals, empty logs. Propose cleanup.

## Steps

1. Run `date` to get current date.
2. Read all data files and check for issues:

### Tasks (`data/canonical/tasks.csv`)
- Tasks with status `queued` and last_updated > 21 days ago → **stale**
- Tasks with status `in_progress` and last_updated > 7 days ago → **stuck**
- Tasks with status `done` but no completion date → **incomplete record**
- Tasks with due_date in the past and status != done → **overdue**
- Count total active tasks — if > 30, flag as backlog bloat

### Habits (`data/canonical/habits.csv` + `logs/daily_log.csv`)
- Habits with 0 logged entries in the past 14 days → **dead habit**
- Habits consistently below 50% of weekly target for 3+ weeks → **struggling**
- Habits with `active=true` but no log entries ever → **never started**

### Goals (`data/canonical/goals.csv`)
- Goals past their target_date with status != done → **missed deadline**
- Goals with no metric_current update in 30+ days → **stale progress**
- Goals with metric_current >= metric_target but status != done → **uncelebrated win**

### Projects (`data/canonical/projects.csv`)
- Projects with no associated tasks in tasks.csv → **empty project**
- Projects with all tasks done but project status still active → **closeable**

### Logs
- Check if daily_log.csv has entries for the past 7 days → flag gaps
- Check if time_logs.csv is being used at all

3. **Generate the audit report** with findings and proposed actions.
4. Ask the user to approve cleanup actions.
5. Apply approved changes.

## Output Format

```
# System Audit — [date]

## Health Score: X/10

### Tasks (X issues)
- Stale: Y tasks untouched for 3+ weeks
- Overdue: Z tasks past due date
- Backlog size: N active tasks [OK / BLOATED]
→ Proposed: drop A, B, C | reschedule D, E

### Habits (X issues)
- Dead: Y habits with no entries in 2 weeks
- Struggling: Z habits below 50% target
→ Proposed: deactivate A | reduce target for B

### Goals (X issues)
- Missed: Y goals past deadline
- Stale: Z goals with no progress update
- Wins to close: W goals at target!
→ Proposed: close A as done | extend deadline for B

### Projects (X issues)
- Empty: Y projects with no tasks
- Closeable: Z projects with all tasks done
→ Proposed: archive A, B

### Logging
- Daily log: [X/7 days this week]
- Time logs: [active / unused]

Apply cleanup? (y/modify/n)
```

## Rules

- Be direct about what's not working. The point of an audit is honesty.
- Suggest dropping things liberally — carrying dead weight is worse than having fewer commitments.
- If the system is healthy, say so briefly and move on. Don't manufacture issues.
- Always update files after approval. Don't just report.
- The health score is subjective but should reflect: are the files being used, is data fresh, are commitments realistic?
