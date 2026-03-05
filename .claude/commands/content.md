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

## Voice & Tone

The user's writing style is casual, direct, and nerdy-confident. Follow these rules:

- **First person, conversational.** Write like talking to a friend, not presenting to a board. Stream-of-consciousness is fine.
- **Specific over vague.** Say "16 commands" not "many commands". Say "CSV files on git" not "a structured system".
- **Self-aware nerd energy.** Lead with "the nerdiest thing about me" not "I'm excited to announce". Embrace the weirdness of what you're building.
- **No corporate buzzwords.** No "leveraging", "synergies", "excited to share", "thrilled to announce", "game-changer". Just say what it is.
- **No em dashes in narrative.** Use commas and periods instead.
- **Anti-overclaiming.** Don't say it changed your life. Say what it actually does and let people decide.
- **Humble confidence.** The work speaks. No "I'm so proud" or "this is amazing". Just describe it matter-of-factly.
- **End with the link, not a CTA.** Don't say "check it out!" or "let me know what you think!" Just drop the link.
- **Emoji only if the user uses them first.** Default to no emoji.
- **The :) is on brand.** Casual closers like "only Anthropic Max :)" are good.

## Rules

- Draw content from real activity — don't invent accomplishments.
- Match tone to platform but always keep the casual, direct voice above.
- If there's no recent activity worth posting about, say so. Don't force content.
- Keep drafts editable — present them as starting points, not final copy.
- Track what gets posted so the user doesn't repeat the same topic across platforms.
