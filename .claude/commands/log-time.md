# /log-time — Log Time Spent

Log actual time spent on an activity to `data/canonical/time_logs.csv`.

## Steps

1. Parse the user's input: activity, duration, domain, optional notes.
2. Run `date` for the current timestamp.
3. Append to `data/canonical/time_logs.csv`.
4. If the activity matches a habit in `habits.csv`, update the habit log in `logs/daily_log.csv`.
5. Confirm what was logged.

## Examples

User: "logged 45 min on Marovi"
→ activity=marovi_build, domain=learning, duration=45, date=today

User: "just did a 30 min workout"
→ activity=workout, domain=health, duration=30, date=today

User: "spent 2 hours on interview prep this morning"
→ activity=interview_prep, domain=learning, duration=120, date=today

## Rules

- Match activity names to existing habits where possible.
- Don't ask for domain if it can be inferred from the activity.
- Keep confirmation brief: "Logged 45 min on Marovi. Total today: 90 min."
