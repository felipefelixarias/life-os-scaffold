# Security Policy

This is a personal-productivity scaffold meant to be forked and run locally.
It has no server, no shared backend, and no multi-tenant boundary — but it
does touch user PII (tasks, habits, calendar data, profile) and a Google
OAuth token. This document covers how to report issues that affect those.

## Supported Versions

The project is pre-1.0 and tracks active development on `main`. Security
fixes land on `main` and are rolled into the next release; older tagged
releases are not patched.

| Version          | Supported          |
| ---------------- | ------------------ |
| `main`           | Yes                |
| Latest `0.x` tag | Yes (best effort)  |
| Older `0.x` tags | No                 |

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security-sensitive reports.
Use GitHub's private vulnerability reporting:

> [Open a private security advisory](https://github.com/felipefelixarias/life-os-scaffold/security/advisories/new)

If GitHub Security Advisories is unavailable for your account, open a
minimal public issue titled "Security report — please contact me" without
details, and the maintainer will follow up to arrange a private channel.

When reporting, please include:

- A description of the issue and the affected file(s) or commit.
- A minimal proof-of-concept or reproduction steps.
- Your assessment of impact (data leak, code execution, denial of service,
  configuration drift, etc.) and any suggested mitigation.

You can expect an initial acknowledgement within roughly seven days. This
is a single-maintainer project, so timelines are best-effort.

## Scope

The following are **in scope**:

- Code in this repository — Python scripts under `01-ops/life-os/scripts/`,
  validation logic, fetchers, and CSV/JSON schema handling.
- The default `.gitignore` patterns that protect personal data and
  credentials (see *Personal-data protections* below).
- Slash-command prompt files under `.claude/commands/` that could induce
  unsafe behavior when invoked through Claude Code.
- Default configuration shipped in `01-ops/life-os/config/*.example.json`.
- Dependency versions pinned in `requirements.txt`, `requirements-dev.txt`,
  and `pyproject.toml`.

The following are **out of scope**:

- Vulnerabilities in third-party services (Google Calendar, Claude Code,
  iCal providers). Report those upstream.
- Issues that require an attacker who already has shell access to the
  user's machine or write access to their fork.
- Personal data committed by a user to their own fork. The scaffold
  protects against this by default, but cannot prevent users from
  overriding `.gitignore`.
- Secrets accidentally committed to a fork. Rotate them and remove from
  history; see [GitHub's guide to removing sensitive
  data](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository).

## Personal-data protections

The default `.gitignore` keeps the following out of git:

- `01-ops/life-os/data/canonical/*.csv` — your tasks, habits, goals,
  projects, calendar events, and time blocks.
- `01-ops/life-os/logs/*.csv` — your time logs and daily entries.
- `01-ops/life-os/outputs/` — generated reports that may contain PII.
- `01-ops/life-os/config/profile.json` and `calendar_feeds.json` — your
  personal configuration.
- `.env` files, `*.pem`, `*.key`, `*credential*.csv`, and
  `*client_secret*.json`.

The Google OAuth token used by the calendar helper lives in
`~/.gcalcli_oauth`, **outside** this repository, so it is never tracked.

If you discover a path that should be ignored but is not — especially a
new file written by a script — please report it.

## Dependency security

`requirements-dev.txt` includes `bandit` and `safety` for local scanning.
Run them with:

```bash
make health        # repo health check, includes dependency review
bandit -r 01-ops/life-os/scripts/
safety check
```

If you spot a vulnerable pinned version in `requirements.txt`,
`requirements-dev.txt`, or `pyproject.toml`, a PR with the upgrade is
welcome alongside (or instead of) a private report.

## Secure-fork checklist

Before pushing a fork to a public remote:

1. Confirm `01-ops/life-os/config/profile.json` is not tracked
   (`git ls-files | grep profile.json` should be empty).
2. Confirm no canonical CSV is tracked
   (`git ls-files 01-ops/life-os/data/canonical/`).
3. If you renamed or repurposed `00-inbox/`, `02-career/`, `03-study/`,
   `05-assets/`, or `06-admin/`, audit them for PII before pushing.
4. Prefer a private repo (see the *Setting up your fork safely* section
   of `README.md`).

Thank you for helping keep life-os users safe.
