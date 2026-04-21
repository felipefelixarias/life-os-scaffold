# Getting Started

## Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed
- Git
- Python 3.12+ (for Google Calendar integration)

## Setup

```bash
git clone https://github.com/felipefelixarias/life-os-scaffold.git life-os
cd life-os
# Install Python dependencies for Google Calendar features
pip install -r requirements.txt
make setup
claude
```

`make setup` copies the example config files into place if you do not have local copies yet.

Then Claude can run `/setup` to fill in your real profile. It asks you about:

1. Name and timezone
2. Wake/sleep schedule and work hours
3. When you're sharpest (builds your energy curve)
4. Life domains to track (career, health, hobbies, etc.)
5. Priority tiers (what's sacred vs what gets cut)
6. Habits to track
7. Current tasks
8. Goals (optional)

Everything gets written to `01-ops/life-os/config/profile.json` and the CSV files under `01-ops/life-os/data/canonical/`.

To re-run setup later: `/setup`

## Verify the Scaffold

```bash
make test
make lint
```

These checks verify the CSV schemas, docs links, command references, and the Python calendar helper.

## Development Setup

If you plan to contribute code, use the full development environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt   # includes base requirements + linting, type-checking, security tools
```

Or use the convenience target:

```bash
make dev-setup
```

### Running Quality Checks Locally

These are the same checks that CI runs on every pull request:

```bash
make test          # pytest (unit + validation tests)
make lint          # repo structure & doc-link checks
ruff check .       # linting
ruff format --check .  # formatting
mypy 01-ops/life-os/scripts/  # type checking
```

Run them all at once with:

```bash
make dev-check     # test + lint + csv-check + health
```

### CI Pipeline

Every push and pull request to `main` triggers a [GitHub Actions workflow](../.github/workflows/ci.yml) that runs:

| Job | What it checks |
|-----|---------------|
| **test** | `pytest` with coverage (≥90% required) |
| **lint** | `ruff` formatting/linting + `mypy` type checks |
| **security** | `bandit` scan for medium/high severity issues |

Fix any CI failures before requesting review.

## Google Calendar (optional)

If you haven't already installed the dependencies:
```bash
pip install -r requirements.txt  # Installs Google API libraries
pip install gcalcli              # Command-line calendar tool
gcalcli list                     # Start OAuth flow
```

Follow the OAuth flow in your browser. Once done, `/turbo` and `/plan-day` can push time blocks to your calendar.

The Python dependencies in `requirements.txt` include:
- `google-auth` and `google-api-python-client` for calendar API access
- `pytest` for running validation tests

See [google-calendar.md](google-calendar.md) for details.

## Daily Usage

**Morning:**
```
/turbo
```
Fetches calendar, shows dashboard, builds day plan, pushes to Google Calendar. One shot.

**During the day:**
```
/add-task fix the login bug, high priority
/log-time 45 min on side project
/replan
```

**End of day:**
```
/shutdown
```
Reviews what happened vs what was planned, updates your files, previews tomorrow.

**End of week:**
```
/weekly-review
```

## All Commands

See [skills-reference.md](skills-reference.md) for the full list of command files included in the scaffold.

## Tips

- **Start small.** Tasks and habits for the first week. Add goals and time logging later.
- **Don't over-track.** Dead data is worse than no data.
- **Weekly review is the keystone.** The habit that makes all other habits work.
- **Trust the tiers.** When time is short, cut from the bottom up.
