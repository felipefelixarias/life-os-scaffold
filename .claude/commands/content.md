# /content — Social Media Content Agent

Plan, draft, and queue social media content across platforms.

## Steps

1. Run `date` to get current date.
2. Read content-related data:
   - `data/canonical/tasks.csv` — filter for content/brand tasks
   - `data/canonical/goals.csv` — filter for brand/content goals
   - `logs/daily_log.csv` — check recent content posting history
3. **Identify content opportunities from recent activity:**
   - Tasks completed this week → potential "building in public" posts
   - Goals with progress updates → milestone posts
   - Habits with strong streaks → "what's working for me" posts
   - Any wins logged → achievement posts
   - Upcoming events or deadlines → anticipation/countdown posts
4. **Check the content queue** (if `data/canonical/content_pipeline.csv` exists):
   - What's already drafted but not posted?
   - What's scheduled for today?
   - What topics have been covered recently (avoid repetition)?
5. **Generate content suggestions** — 3-5 post ideas with:
   - Platform (LinkedIn, X, Instagram, TikTok)
   - Hook (first line / caption opener)
   - Key point
   - Call to action
   - Format (text, carousel, short video, story)
6. If the user picks one, draft the full post.
7. If `data/canonical/content_pipeline.csv` exists, append the draft to the queue.

## Output Format

```
# Content Ideas — [date]

## Recent Activity to Post About
- [completed task / milestone / win]

## Suggestions

### 1. [Platform] — [Topic]
**Hook:** "..."
**Key point:** ...
**CTA:** ...
**Format:** text post

### 2. [Platform] — [Topic]
...

## Queue Status
- Drafted: X posts
- Posted this week: Y
- Target: Z/week

Pick a number to draft, or describe what you want to post.
```

## Rules

- Draw content from real activity — don't invent accomplishments.
- Match tone to platform (LinkedIn = professional insight, X = punchy takes, Instagram = visual/personal, TikTok = raw/authentic).
- If there's no recent activity worth posting about, say so. Don't force content.
- Keep drafts editable — present them as starting points, not final copy.
- Track what gets posted so the user doesn't repeat the same topic across platforms.
