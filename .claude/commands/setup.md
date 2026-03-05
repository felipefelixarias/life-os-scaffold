# /setup — First-Time Setup Questionnaire

Walk a new user through setting up their life-os. This runs once to populate their profile, domains, habits, and first tasks.

## Steps

1. Check if `01-ops/life-os/config/profile.json` exists. If it does, ask: "Profile already exists. Re-run setup or skip?" If skip, exit.
2. If it doesn't exist, copy `01-ops/life-os/config/profile.example.json` → `01-ops/life-os/config/profile.json`.
3. Run `date` to detect the user's system timezone.

## Questionnaire

Ask these questions **one section at a time**, not all at once. Fill in profile.json as you go.

### Section 1: Basics
```
What's your name?
What timezone are you in? (detected: [system timezone] — confirm or change)
```

### Section 2: Schedule
```
What time do you wake up on weekdays?
What time do you wake up on weekends?
Do you have a regular work schedule? If so, what hours? (e.g., 9-5, remote, shift work, student)
What time do you go to bed?
```

### Section 3: Energy
```
When during the day are you sharpest / most focused? (morning, afternoon, evening, late night)
When do you hit an energy low? (after lunch, mid-afternoon, etc.)
Do you get a second wind? When?
```
Use the answers to build the `energy_curve` array in profile.json.

### Section 4: Life Domains
```
What are the main areas of your life you want to track?
(Examples: career, health, learning, hobbies, finance, relationships, side project)
Just list them — I'll set up the structure.
```
Create the `domains` array. Ask them to rank by importance (or suggest a ranking and let them adjust).

### Section 5: Priority Tiers
Explain the concept briefly:
```
When your day gets shorter than planned, what's sacred and what gets cut?
- Tier 1 (never cut): e.g., sleep, medication, critical deadlines
- Tier 2 (protect): e.g., main project, exercise
- Tier 3 (important but flexible): e.g., learning, content
- Tier 4 (nice to have): e.g., extra hobbies, cleanup
- Tier 5 (cut first): e.g., extended sessions, low-priority admin
```
Ask them to fill in their own tiers, or suggest defaults and let them adjust.

### Section 6: Habits
```
What habits do you want to track? For each one:
- Name
- How many times per week?
- How long per session? (or just a checkbox)
```
Write these to `01-ops/life-os/data/canonical/habits.csv`.

### Section 7: First Tasks
```
What are 3-5 things on your plate right now?
```
Parse into tasks and write to `01-ops/life-os/data/canonical/tasks.csv`.

### Section 8: Goals (optional)
```
Any goals you're working toward? (e.g., "run a marathon by December", "ship my app by Q3")
Skip this if you'd rather add goals later.
```
If provided, write to `01-ops/life-os/data/canonical/goals.csv`.

## After Setup

1. Write the completed profile.json.
2. Confirm what was created:
   ```
   Setup complete!

   Profile: 01-ops/life-os/config/profile.json
   Habits: X habits tracked
   Tasks: Y tasks added
   Goals: Z goals set

   Try these next:
   - /turbo — run your first morning dashboard + day plan
   - /add-task — add more tasks anytime
   - /status — quick pulse check
   ```

## Rules

- Be conversational but efficient. Don't over-explain each question.
- Suggest smart defaults based on what they've already said (e.g., if they're a student, don't assume 9-5 work hours).
- If they say "skip" or "later" for any section, move on. Don't push.
- Write files as you go, not all at the end. If the session crashes mid-setup, partial progress is saved.
- For energy curve, translate natural language ("I'm a morning person") into the structured format.
- For habits, infer domain from context (e.g., "workout" → health, "read papers" → learning).
