# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Scheduled for the upcoming 0.2.0 release. Grouped by Keep-a-Changelog category;
commits accumulated on `main` since the 0.1.0 tag (2026-03-09).

### Added
- Declarative CSV schema validation covering every canonical data file, with a
  single source-of-truth module (`01-ops/life-os/scripts/csv_schemas.py`) and
  100% line coverage on its tests.
- Declarative foreign-key schemas so cross-file relationships (tasks ↔ goals,
  time_logs ↔ tasks, etc.) validate against a single definition rather than
  ad-hoc per-script logic.
- Configuration file validation schemas for `config/profile.json` and
  `config/calendar_feeds.json`, plus a `validate_config.py` entry point.
- Opt-in integration tests for the Google Calendar API
  (`tests/test_gcal_integration.py`) — gated behind
  `@pytest.mark.integration`, `LIFE_OS_GCAL_INTEGRATION=1`,
  `LIFE_OS_GCAL_TEST_CALENDAR_ID`, and a present `~/.gcalcli_oauth` so CI
  auto-skips with zero config.
- Contributor development setup guide (`CONTRIBUTING.md` expansions) and a CI
  status badge in `README.md`.
- Pre-commit hooks (`ruff`, `black`, `mypy`, `bandit`) and a
  `requirements-dev.txt` capturing the dev toolchain.
- Development utilities: `check_csv_data.py` CSV inspector, `repo_health.py`
  health check, and a `csv-check` Make target.

### Changed
- Consolidated CSV schema definitions, numeric constraints, and time-field
  rules into `csv_schemas.py`; `validate_repo.py` and `validate_csv_integrity.py`
  now delegate to the shared schema rather than duplicating rules.
- Optimized CSV validation with pre-compiled regex patterns, cached reads, and
  O(1) lookups; eliminated duplicate CSV reads in foreign-key validation.
- Modernized the test suite: migrated fixtures to pytest `tmp_path`, converted
  unittest-style assertions to pytest idioms, and reorganized test modules.
- Hardened `gcal.py`: improved OAuth token handling, narrowed exception scopes,
  added structured logging for API errors.
- Aligned canonical CSV schemas (`tasks`, `habits`, `time_logs`, `goals`,
  enums for priority/status/source/domain/frequency) with the documented
  schemas in `docs/csv-schemas.md`.
- Aligned `make lint` and `make test` targets with the checks formerly run in
  CI, so local runs mirror the gate the maintainer uses before tagging.
- Raised the Python requirement to 3.12+ in both `README.md` and
  `pyproject.toml` (matching the already-in-use 3.12 classifier).

### Fixed
- Broken file-path references in `.claude/commands/*.md` and other command
  files; added `check_command_paths.py` to guard against regressions.
- Habits schema required/type mismatches and incorrect frequency enum values
  in `docs/customization.md`.
- Missing `workday_start` / `workday_end` profile fields in
  `docs/customization.md`.
- CSV data quality issues in canonical example files.
- Proper exit codes and narrower exception handling in CLI scripts
  (`validate_repo.py`, `check_csv_data.py`, `check_dependencies.py`).
- Critical bug: restored the missing `LIFE_OS_TAG` constant used by
  `gcal.clear_life_os_events()`.
- `/improve` command now uses the full path for the outputs directory instead
  of a relative path that broke when invoked from subdirectories.

### Removed
- GitHub Actions workflows (`.github/workflows/`). CI was disabled because
  transient failures were generating noisy "failing-CI" email notifications;
  the previously-CI-enforced checks (mypy, ruff, bandit, pytest with coverage)
  now run via `make lint` and `make test` locally and in pre-commit. No
  project-level check was dropped — only the hosted runner was removed.

### Testing
- Core module coverage: 87% → 94% → 97% → 99% → **100%** on
  `csv_schemas.py` and `gcal.py`; repo-wide coverage at ~99%.
- 373+ test cases across unit and (opt-in) integration suites.

## [0.1.0] - 2026-03-31

- Initial release.
