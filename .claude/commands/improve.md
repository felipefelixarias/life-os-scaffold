# /improve — System Improvement Agent

Analyze how the life-os system is being used, identify friction, and suggest or implement improvements to commands, schemas, and workflows.

## Steps

1. Run `date`.
2. **Analyze system usage patterns:**
   - Read `logs/activity_log.csv` — which commands are used most/least?
   - Read `logs/daily_log.csv` — how consistently is the system being used?
   - Read all `data/canonical/*.csv` files — which schemas have data, which are empty?
   - Check `outputs/` — what's being generated?
3. **Identify friction points:**
   - Commands that are never used → maybe they're not useful or too hard to trigger
   - Data files that are always empty → schema might not match the user's workflow
   - Habits or tasks that are always carried/missed → the system is tracking aspirations, not reality
   - Frequent manual edits to CSVs that could be automated
4. **Check for missing capabilities:**
   - Is there a workflow the user does repeatedly that doesn't have a command?
   - Are there data relationships that should be tracked but aren't? (e.g., task → time spent)
   - Would a new CSV schema, template, or command help?
5. **Propose improvements** in three categories:
   - **Quick fixes**: config tweaks, habit target adjustments, priority reordering
   - **New commands**: slash commands or agents that would automate a repetitive workflow
   - **Schema changes**: new CSV columns, new data files, restructured relationships
6. If the user approves, implement the changes directly.

## Output Format

```
# System Improvement — [date]

## Usage Summary
- Most used: /daily (X times), /plan-day (Y times)
- Never used: /log-time, /status
- Data coverage: tasks (full), habits (full), time_logs (empty), goals (sparse)

## Friction Points
1. [problem] — [evidence] → [suggested fix]
2. ...

## Proposed Improvements

### Quick Fixes
- [ ] Adjust workout habit target from 5/wk to 3/wk (actual average: 2.5)
- [ ] Add "energy" column to daily_log for tracking patterns

### New Commands
- [ ] `/focus` — start a timed deep work session with task context
- [ ] `/habits` — quick habit check-in without the full dashboard

### Schema Changes
- [ ] Add `actual_effort_mins` to tasks.csv for planned vs actual tracking

Implement any of these? (list numbers or "all")
```

## Rules

- Base suggestions on actual data, not assumptions.
- Don't suggest changes that add complexity without clear value.
- If the system is working well, say so. Not every session needs improvements.
- When implementing changes, update all affected files (commands, CLAUDE.md, schemas).
- If suggesting a new command, write the full markdown file — don't just describe it.
