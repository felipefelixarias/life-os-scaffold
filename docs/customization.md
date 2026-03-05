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
Define when your day starts, when work happens, and when you sleep.
```json
"planning": {
  "weekday_wake": "07:00",
  "weekend_earliest": "09:00",
  "day_end": "23:00",
  "bedtime": "23:00",
  "workday_start": "09:00",
  "workday_end": "17:00"
}
```

### Energy Curve
The planner schedules deep work during high-energy periods and admin during lows. Adjust the times and levels to match your actual rhythm — not what you wish it was.
```json
"energy_curve": [
  {"time": "07:00", "energy": "low"},
  {"time": "09:00", "energy": "high"},
  {"time": "14:00", "energy": "low"},
  {"time": "19:00", "energy": "high"}
]
```

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
- `frequency`: daily, weekday, weekend, or specific days
- `target_per_week`: how many times per week
- `min_value`: minimum session length/count
- `unit`: minutes, reps, checks, etc.

Don't over-track. Only add habits you'll actually review. Dead data is worse than no data.

## Skills (`.claude/commands/`)

Skills are markdown files that register as slash commands in Claude Code. Each file describes:
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

## Calendar Feeds (`01-ops/life-os/config/calendar_feeds.json`)

If you have ICS feed URLs (from Google Calendar, Outlook, etc.), add them here for automatic import:

```json
[
  {
    "name": "Work",
    "url": "https://calendar.google.com/calendar/ical/YOUR_ID/basic.ics",
    "color": "blue"
  }
]
```

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
