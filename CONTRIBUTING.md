# Contributing to life-os-scaffold

Thanks for your interest in improving life-os! Here's how to contribute effectively.

## Before You Start

- **Read the [README.md](README.md)** to understand the project's goals and structure
- **Browse existing issues** to see if your idea has already been discussed
- **Try the system** for a week to understand how it works in practice

## Types of Contributions

### 🐛 Bug Fixes
- Broken commands or validation scripts
- CSV schema issues
- Documentation errors
- Google Calendar integration problems

### 📝 Documentation
- Command improvements (clearer prompts, better examples)
- Guide updates (getting started, customization)
- Schema documentation

### ✨ New Features
- New slash commands for common workflows
- Additional CSV schemas for tracking new data
- Integrations with other tools
- Validation improvements

## Development Setup

1. Fork the repository (create a private fork for personal data safety)
2. Clone your fork:
```bash
git clone https://github.com/YOUR_USERNAME/life-os-scaffold.git
cd life-os-scaffold
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Verify your setup:
```bash
make test
make lint
```

## Making Changes

### Branch Naming
- `fix/issue-description` for bug fixes
- `feature/feature-name` for new features  
- `docs/update-description` for documentation

### Code Quality Standards
All code must meet these standards before submission:

1. **Tests pass**: `make test` should complete without errors
2. **Validation passes**: `make lint` should pass all checks
3. **Type annotations**: All Python functions should have type hints
4. **Error handling**: Handle edge cases gracefully, don't crash
5. **Documentation**: Update relevant docs when changing behavior

### CSV Schema Changes
If you modify any CSV schemas:

1. Update the validation script (`01-ops/life-os/scripts/validate_repo.py`)
2. Add tests for the new schema in `tests/test_repo_validation.py`  
3. Update documentation in `docs/csv-schemas.md`
4. Test with real data, not just empty files

### Command Changes
If you modify slash commands:

1. Update the command file in `.claude/commands/`
2. Test the command manually with Claude
3. Update the command list in `README.md` if needed
4. Add any new command references to docs

## Testing Your Changes

```bash
# Run all tests
make test

# Run validation with lint checks
make lint

# Test a specific component
python3 -m pytest tests/test_repo_validation.py -v

# Test Google Calendar integration (if configured)
make gcal-test
```

### Google Calendar Integration Tests

`tests/test_gcal_integration.py` exercises the real Google Calendar API. It is
**opt-in** and skipped in CI. To run it locally:

1. Authenticate `gcalcli` once so `~/.gcalcli_oauth` exists:
   ```bash
   gcalcli list
   ```
2. Create a **dedicated test calendar** in Google Calendar (do NOT point these
   tests at your primary calendar — `clear_life_os_events()` will remove every
   event tagged `[life-os]` on the target date).
3. Copy the test calendar's ID (Settings → Integrate calendar → Calendar ID)
   and run:
   ```bash
   LIFE_OS_GCAL_INTEGRATION=1 \
   LIFE_OS_GCAL_TEST_CALENDAR_ID=<your-test-calendar-id> \
   pytest tests/test_gcal_integration.py -v
   ```

Without both env vars set, every test in the file is skipped, so leaving the
suite enabled in CI is safe. To run only the mock-based unit tests locally, use
`pytest -m "not integration"`.

## Submitting Changes

1. **Create a pull request** with:
   - Clear description of what changed and why
   - Link to any related issues
   - Screenshots for UI changes

2. **PR title format**: `[type] Brief description`
   - `[fix]` for bug fixes
   - `[feat]` for new features  
   - `[docs]` for documentation
   - `[test]` for test improvements

3. **Include testing notes** in the PR description:
   - What you tested
   - Any edge cases you considered
   - Instructions for reviewers to test

## Review Process

- Maintainers will review your PR within a few days
- You may be asked to make changes
- Once approved, your changes will be merged

## Questions?

- Open an issue for questions about the system or contributing
- Check existing issues first to avoid duplicates
- For complex features, open an issue to discuss before implementing

## Code of Conduct

- Be respectful and constructive in discussions
- Focus on the technical aspects of contributions
- Help create a welcoming environment for all contributors

Thanks for helping make life-os better! 🚀