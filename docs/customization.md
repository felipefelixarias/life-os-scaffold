# Customization

life-os is a scaffold, not a product. It's designed to be shaped around your actual life. Here's how to make it yours.

## Profile (`01-ops/life-os/config/profile.json`)

This is the single most important file. It tells the planner who you are.

### Timezone
Set this to your IANA timezone. All scheduling and calendar operations depend on it.
```json
"timezone": "America/New_York"
```

### Planning Windows
Define when your day starts, when work happens, and when you sleep. Also configure default task durations and scheduling parameters.
```json
"planning": {
  "weekday_wake": "07:00",
  "weekend_earliest": "09:00",
  "day_end": "23:00",
  "bedtime": "23:00",
  "workday_start": "09:00",
  "workday_end": "17:00",
  "workday_commute_start": "08:30",
  "workday_commute_home_end": "17:30",
  "default_task_block_mins": 60,
  "deep_work_block_mins": 90,
  "max_screen_block_mins": 90,
  "break_mins": 15,
  "max_major_tasks_per_day": 4,
  "weekly_review_day": "Sunday"
}
```

**Additional Planning Fields:**
- `workday_start`: When your work day begins (for scheduling work blocks)
- `workday_end`: When your work day ends
- `workday_commute_start`: When to leave for work (for commuters)
- `workday_commute_home_end`: When you arrive home from work
- `default_task_block_mins`: Default time allocation for standard tasks
- `deep_work_block_mins`: Duration for focused work sessions
- `max_screen_block_mins`: Maximum continuous screen time
- `break_mins`: Standard break duration between tasks
- `max_major_tasks_per_day`: Limit on high-effort tasks per day
- `weekly_review_day`: Day of week for weekly planning review

### Energy Curve
The planner schedules deep work during high-energy periods and admin during lows. Adjust the times and levels to match your actual rhythm — not what you wish it was.
```json
"energy_curve": [
  {"time": "07:00", "energy": "low"},
  {"time": "09:00", "energy": "high"},
  {"time": "12:00", "energy": "medium"},
  {"time": "14:00", "energy": "low"},
  {"time": "16:00", "energy": "medium"},
  {"time": "19:00", "energy": "high"},
  {"time": "21:00", "energy": "medium"},
  {"time": "22:00", "energy": "low"}
]
```

This 8-point curve captures typical energy patterns: morning rise, lunch dip, afternoon recovery, evening peak, and nighttime wind-down. Customize the timing and levels based on your personal patterns.

### Domains
Domains are the life areas you track. Weight determines relative priority when the planner allocates time.
```json
"domains": [
  {"id": "career", "name": "Career", "weight": 10},
  {"id": "health", "name": "Health", "weight": 9},
  {"id": "hobbies", "name": "Hobbies", "weight": 7}
]
```

### Priority Tiers
When the day gets shorter than planned, the planner cuts from the bottom up. Define what's sacred and what's expendable.
```json
"priority_tiers": [
  {"tier": 1, "label": "Non-negotiable", "examples": "sleep, health essentials"},
  {"tier": 2, "label": "Core build", "examples": "main project, exercise"},
  {"tier": 3, "label": "Growth", "examples": "learning, content"},
  {"tier": 4, "label": "Nice to have", "examples": "extra hobbies, cleanup"},
  {"tier": 5, "label": "Cut first", "examples": "extended sessions, admin"}
]
```

## Numbered Directories

The top-level structure uses numbered prefixes for sort order. Customize these to match your life:

- Rename `02-career/` to `02-music/` if you're a musician, not a job-seeker
- Add `07-health/` if health tracking deserves its own top-level bucket
- Remove directories you don't need (but keep `01-ops/life-os/` as the engine)
- The numbers just control sort order in `ls`. Pick whatever makes sense.

## Habits (`01-ops/life-os/data/canonical/habits.csv`)

Add rows for anything you want to track regularly. Fields:
- `habit_id`: unique slug (e.g., `workout`, `read_30m`)
- `area`: domain it belongs to
- `frequency`: `daily` or `weekly`
- `target_per_week`: how many times per week
- `min_value`: minimum session length/count
- `unit`: minutes, reps, checks, etc.

Don't over-track. Only add habits you'll actually review. Dead data is worse than no data.

## Skills (`.claude/commands/`)

Skills are markdown files that register as slash commands in Claude Code. In this scaffold they are the primary implementation surface. Each file describes:
- What the skill does
- Step-by-step instructions
- Output format
- Rules and constraints

### Writing a New Skill

Create a markdown file in `.claude/commands/`:

```markdown
# /my-skill — Short Description

Brief explanation of what this does.

## Steps

1. What to read or check first
2. What to compute or generate
3. What to output or write

## Output Format

What the user should see.

## Rules

- Constraints and edge cases
```

Name the file to match the command: `.claude/commands/my-skill.md` → `/my-skill`.

### Skill Ideas
- `/meal-plan` — Weekly meal planning based on dietary goals
- `/study` — Study session with spaced repetition prompts
- `/budget` — Monthly spending review from a transactions CSV
- `/workout` — Generate a workout plan based on available equipment and goals
- `/journal` — Guided evening reflection prompts

## Templates (`01-ops/life-os/templates/`)

Templates are markdown files used for recurring documents (sprints, check-ins). Modify them to ask the questions that matter to you.

## Calendar Feeds

If you have ICS feed URLs (from Google Calendar, Outlook, etc.), create
`01-ops/life-os/config/calendar_feeds.json` (or `make setup` copies
`calendar_feeds.example.json` for you) so life-os can pull external calendars:

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
      "output_file": "work.ics",
      "timeout_seconds": 30
    }
  ]
}
```

- `name` — short label shown in logs.
- `enabled` — only `true` feeds are fetched.
- `url` — must start with `http://` or `https://`.
- `output_file` — plain filename (no path separators); written under
  `01-ops/life-os/data/feeds/`.
- `timeout_seconds` — fetch timeout in seconds, 1–300.

The file is validated against `config_schemas.CALENDAR_FEEDS_SCHEMA` at load
time, so typos surface immediately instead of failing silently during a fetch.
See [docs/google-calendar.md](google-calendar.md) for the full fetcher
workflow.

## Adding a New Domain

1. Add the domain to `profile.json` under `domains`
2. Add relevant habits to `habits.csv`
3. Add goals to `goals.csv`
4. Optionally create a skill for domain-specific workflows

## Tips

- **Start minimal.** Use tasks and habits for a week before adding goals, time logging, or sprints.
- **Review weekly.** The `/weekly-review` skill is the keystone. It's the habit that makes all other habits work.
- **Iterate the profile.** Your energy curve, tiers, and domains will change. Update them as you learn what actually works.
- **Git is your changelog.** Commit your CSVs regularly. The diff history is your life log.
