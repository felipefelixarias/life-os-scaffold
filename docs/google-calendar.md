# Google Calendar Integration

## Overview

life-os can read and write Google Calendar events directly from your terminal. This scaffold includes a small helper module plus Make targets for connectivity checks. That enables:
- Viewing your agenda as part of `/daily`
- Pushing time-blocked day plans to your calendar
- Creating events with `/gcal-create`
- Cleaning up and replanning with `/replan`

## Setup

### 1. Install gcalcli

```bash
pip install gcalcli
```

### 2. Authenticate

```bash
gcalcli list
```

This opens a browser for Google OAuth. Sign in and grant calendar access. The OAuth token is typically saved to `~/.gcalcli_oauth` as a pickle file.

> **Note:** gcalcli v4.4+ requires your own Google Cloud OAuth credentials. See [gcalcli docs](https://github.com/insanum/gcalcli#login-information) for details on setting up a Google Cloud project with the Calendar API enabled.

### 3. Verify

```bash
gcalcli agenda
```

You should see your upcoming events. If this works, life-os can read your calendar.

### 4. Test from life-os

```bash
make gcal-test
```

## How It Works

life-os uses two approaches to interact with Google Calendar:

1. **gcalcli CLI** — for quick reads (`gcalcli agenda`), used by skills like `/daily`
2. **`01-ops/life-os/scripts/gcal.py`** — a Python wrapper around the Google Calendar API, used for creating, updating, and deleting events

The Python wrapper (`01-ops/life-os/scripts/gcal.py`) reuses gcalcli's saved OAuth token at `~/.gcalcli_oauth`, so you only authenticate once.

## What `01-ops/life-os/scripts/gcal.py` Provides

| Function | Description |
|----------|-------------|
| `get_agenda(start, end)` | List events between two dates |
| `create_event(summary, start, end, ...)` | Create a single event |
| `update_event(event_id, **kwargs)` | Update event fields |
| `delete_event(event_id)` | Delete an event |
| `search_events(query, start, end)` | Search events by text |
| `push_day_plan(blocks, date)` | Batch-create time blocks for a day |
| `list_calendars()` | List all available calendars |

All functions use the timezone from your `01-ops/life-os/config/profile.json`. The helper resolves IANA zones through Python's timezone database, so non-US zones such as `Europe/Paris` work correctly too.

## Day Plan Push

When you run `/plan-day` and approve the plan, life-os pushes each time block as a separate Google Calendar event. These events are tagged with `[life-os]` in the description field.

When you `/replan`, life-os first deletes all `[life-os]`-tagged events for the day, then creates the new plan. This prevents duplicate events from stacking up.

## Timezone

All calendar operations use the timezone specified in `01-ops/life-os/config/profile.json`. Make sure this matches your Google Calendar's primary timezone to avoid offset issues.

## External iCal Feeds (Outlook, iCloud, CalDAV, …)

Google Calendar is only one of the providers life-os can read. Any service that
publishes a public iCal (`.ics`) subscription URL — Outlook/Office 365, Apple
iCloud, Fastmail, meetup.com, a team CalDAV server, etc. — can be pulled in
through `fetch_calendar_feeds.py`.

### Configure

After `make setup`, edit `01-ops/life-os/config/calendar_feeds.json`:

```json
{
  "feeds": [
    {
      "name": "personal",
      "enabled": true,
      "url": "https://calendar.google.com/calendar/ical/YOUR_ID/basic.ics",
      "output_file": "personal.ics",
      "timeout_seconds": 30
    },
    {
      "name": "work",
      "enabled": false,
      "url": "https://outlook.office365.com/owa/calendar/YOUR_ID/calendar.ics",
      "output_file": "work.ics"
    }
  ]
}
```

Only feeds with `"enabled": true` are fetched. `output_file` must be a plain
filename (no path separators, no `..`); each feed is written under
`01-ops/life-os/data/feeds/`.

### Run

```bash
make feeds-fetch
# or, directly:
python3 01-ops/life-os/scripts/fetch_calendar_feeds.py \
    --config 01-ops/life-os/config/calendar_feeds.json \
    --output-dir 01-ops/life-os/data/feeds
```

The script exits `0` when every enabled feed downloaded, `1` when at least one
failed (remaining feeds still complete), and `2` when the config file is
missing or malformed. Each download is atomic — partial writes are discarded,
so a mid-transfer failure never leaves a truncated `.ics` file in place.

### Safety guards

- Only `http://` and `https://` URLs are accepted; `file://`, `ftp://`, etc.
  are rejected before any network call.
- Responses larger than 50 MiB are aborted and the partial file is deleted.
- A `User-Agent` header identifies life-os in server logs.

## Troubleshooting

**"No OAuth token" error**
Run `gcalcli list` to re-authenticate.

**Events show wrong time**
Check that `timezone` in `01-ops/life-os/config/profile.json` matches your actual timezone (e.g., `America/New_York`, `America/Los_Angeles`, `Europe/Paris`).

**"Access blocked" during OAuth**
If using your own Google Cloud project, make sure:
- Calendar API is enabled
- OAuth consent screen is configured
- Your Google account is added as a test user (or the app is published)

**gcalcli not found**
Make sure the install location is on your PATH. Common locations:
- macOS: `~/Library/Python/3.X/bin/`
- Linux: `~/.local/bin/`
