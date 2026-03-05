# /gcal-create — Create a Google Calendar Event

Create an event on Google Calendar from natural language.

## Prerequisites

- gcalcli installed and authenticated (`~/.gcalcli_oauth` exists)
- `scripts/gcal.py` available

## Steps

1. Parse the user's input: event title, date, start time, end time, location (optional).
2. Run `date` to resolve relative dates ("tomorrow", "this Saturday").
3. Read `config/profile.json` for timezone.
4. Create the event using `scripts/gcal.py` or the Google Calendar API directly.
5. Confirm: event name, date, time, location.

## Examples

User: "add dinner at The Morris Saturday at 6pm"
→ title=Dinner at The Morris, date=Saturday, start=18:00, end=19:30, location=The Morris

User: "block 2-4pm tomorrow for deep work"
→ title=Deep Work, date=tomorrow, start=14:00, end=16:00

User: "remind me to leave for the airport at 3pm on March 21"
→ title=Leave for Airport, date=2026-03-21, start=15:00, end=15:15, reminder=5min

## Rules

- Default event duration: 1 hour if not specified.
- Always use the profile timezone for all datetime operations.
- If location is given, include it in the event.
- Confirm before creating — show what you're about to add.
