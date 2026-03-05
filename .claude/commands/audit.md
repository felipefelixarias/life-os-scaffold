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

Health score as a big visual gauge. Each subsystem gets a status line.

```
  ╔══════════════════════════════════════════════════════════════════╗
  ║                life-os · audit · [date]                        ║
  ╚══════════════════════════════════════════════════════════════════╝

  HEALTH    ████████████████░░░░  8 / 10

  SUBSYSTEM          STATUS    ISSUES
  ─────────────────────────────────────────────────────────
  Tasks              ██████░░  2 stale · 1 overdue · 18 active
  Habits             ████████  all on track
  Goals              ██████░░  1 stale progress · 1 uncelebrated win
  Projects           ████░░░░  2 empty · 1 closeable
  Daily log          ████████  7/7 days
  Time logs          ░░░░░░░░  unused

  ┌─ findings ─────────────────────────────────────────────────────┐
  │                                                                 │
  │  TASKS                                                          │
  │  ✗ "Update deployment docs"       stale 24d → drop?            │
  │  ✗ "Research caching layer"       stale 18d → drop?            │
  │  ⚠ "Submit expense report"        3d overdue → reschedule?     │
  │                                                                 │
  │  GOALS                                                          │
  │  ⚠ "Launch Marovi beta"           no update in 32d             │
  │  ★ "Hit 5 PR reviews/week"        at target! → close as done   │
  │                                                                 │
  │  PROJECTS                                                       │
  │  ✗ "Old hackathon"                0 tasks → archive?           │
  │  ✗ "Q1 planning"                  all done → close?            │
  │                                                                 │
  └─────────────────────────────────────────────────────────────────┘

  Apply cleanup? (y/modify/n)
```

## Rules

- Be direct about what's not working. The point of an audit is honesty.
- Suggest dropping things liberally — carrying dead weight is worse than having fewer commitments.
- If the system is healthy, say so briefly and move on. Don't manufacture issues.
- Always update files after approval. Don't just report.
- The health score is subjective but should reflect: are the files being used, is data fresh, are commitments realistic?
