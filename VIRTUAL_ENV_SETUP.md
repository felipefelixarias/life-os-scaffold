# Virtual Environment Setup Guide

This document provides instructions for setting up a proper Python virtual environment for the life-os-scaffold project.

## Quick Setup

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Verify installation
python3 -m pytest tests/ -v
```

## Dependencies Overview

The project requires several Google API packages for Calendar integration:

### Core Google API Dependencies
- `google-auth>=2.30.0,<3.0.0` - Google authentication library
- `google-api-python-client>=2.120.0,<3.0.0` - Google API client library  
- `google-auth-oauthlib>=1.2.0,<2.0.0` - OAuth flow for Google APIs
- `google-auth-httplib2>=0.2.0,<1.0.0` - HTTP transport for Google Auth

### Development Dependencies  
- `pytest>=8.0.0,<9.0.0` - Testing framework
- `pytest-cov>=4.0.0,<6.0.0` - Coverage reporting

### Utility Dependencies
- `python-dateutil>=2.8.0,<3.0.0` - Date/time utilities
- `requests>=2.31.0,<3.0.0` - HTTP library

## Installing Without Virtual Environment

If you encounter "externally-managed-environment" errors, you have several options:

### Option 1: System packages (Ubuntu/Debian)
```bash
sudo apt install python3-pip python3-venv
sudo apt install python3-google-auth python3-googleapi python3-pytest
```

### Option 2: Override system protection (not recommended)
```bash
pip install -r requirements.txt --break-system-packages
```

### Option 3: User installation
```bash
pip install --user -r requirements.txt
```

## Verification Commands

After setup, verify everything works:

```bash
# Run all tests
make test

# Run specific test suites  
python3 -m pytest tests/test_gcal.py -v
python3 -m pytest tests/test_check_csv_data.py -v
python3 -m pytest tests/test_repo_validation.py -v

# Check test coverage
python3 -m pytest --cov=. --cov-report=term-missing tests/

# Run health check
make health

# Check dependencies
make deps-check
```

## Google Calendar Setup

The Google Calendar integration requires additional setup:

1. Install and authenticate `gcalcli`:
   ```bash
   pip install gcalcli
   gcalcli list  # This will prompt for authentication
   ```

2. Verify OAuth token location:
   ```bash
   ls -la ~/.gcalcli_oauth
   ```

3. Test Google Calendar connectivity:
   ```bash
   make gcal-test
   ```

## Troubleshooting

### Missing Dependencies
If `make deps-check` shows missing packages:
```bash
source .venv/bin/activate  # if using venv
pip install -r requirements.txt
```

### Permission Errors
If you get permission errors accessing Google Calendar:
```bash
chmod 600 ~/.gcalcli_oauth
```

### Import Errors in Tests
If tests fail with import errors, ensure virtual environment is activated:
```bash
source .venv/bin/activate
which python3  # Should point to .venv/bin/python3
```

### gcalcli Not Found
```bash
# In virtual environment
pip install gcalcli

# Or system-wide
sudo apt install gcalcli  # Ubuntu/Debian
brew install gcalcli      # macOS
```

## Development Workflow

Recommended workflow for development:

```bash
# Activate environment
source .venv/bin/activate

# Run development checks
make dev-check

# Run specific validations
make lint
make test  
make csv-check
make health

# When done developing
deactivate  # Exit virtual environment
```

## Notes

- The virtual environment should be created in the repository root as `.venv/`
- Add `.venv/` to `.gitignore` (already done)
- Always activate the virtual environment before running tests or development commands
- The Google API dependencies are required for the calendar integration features to work properly