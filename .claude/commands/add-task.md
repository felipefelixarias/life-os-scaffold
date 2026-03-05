# /add-task — Quick Task Capture

Add a task to `data/canonical/tasks.csv` from a natural language description.

## Steps

1. Parse the user's input to extract: title, domain, priority, effort estimate, due date.
2. Generate a `task_id` from the title (slugified, with date suffix).
3. Infer reasonable defaults for any missing fields:
   - Priority: 2 (medium) unless urgency words are used
   - Effort: 60 mins unless specified
   - Domain: infer from context (e.g., "workout" → health, "ship feature" → career)
   - Energy: medium unless specified
   - Status: queued
4. Append the row to `data/canonical/tasks.csv`.
5. Confirm what was added.

## Examples

User: "add task: buy groceries, low priority"
→ title=Buy groceries, domain=personal, priority=3, effort=30, energy=low

User: "I need to review the PR by Friday"
→ title=Review PR, domain=career, priority=1, due_date=Friday, effort=45, energy=high

User: "remind me to call mom this weekend"
→ title=Call mom, domain=relationships, priority=2, due_date=Saturday, effort=15, energy=low

## Rules

- Don't ask clarifying questions for obvious defaults. Just add it and confirm.
- If the user gives a vague due date ("this week", "soon"), convert to a concrete date.
- Always confirm what was added so the user can correct if needed.
