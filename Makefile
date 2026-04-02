.PHONY: help setup test lint clean gcal-agenda gcal-test

LIFE_OS := 01-ops/life-os

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: ## Copy example configs and get started
	@test -f $(LIFE_OS)/config/profile.json || (cp $(LIFE_OS)/config/profile.example.json $(LIFE_OS)/config/profile.json && echo "Created profile.json — edit it with your details")
	@test -f $(LIFE_OS)/config/calendar_feeds.json || (cp $(LIFE_OS)/config/calendar_feeds.example.json $(LIFE_OS)/config/calendar_feeds.json && echo "Created calendar_feeds.json — add your calendar URLs")
	@echo "Setup complete. Run 'claude' to start using life-os."

test: ## Run repo validation and unit tests
	@python3 $(LIFE_OS)/scripts/validate_repo.py
	@python3 -m unittest discover -s tests

lint: ## Run lightweight lint checks for docs and scaffold integrity
	@python3 $(LIFE_OS)/scripts/validate_repo.py --lint

clean: ## Remove generated Python cache files
	@find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	@rm -rf .coverage .pytest_cache htmlcov

gcal-agenda: ## Show today's Google Calendar agenda
	@gcalcli agenda "$$(date +%Y-%m-%d)" "$$(python3 -c 'import datetime as dt; print((dt.date.today() + dt.timedelta(days=1)).isoformat())')" 2>/dev/null || echo "gcalcli not configured. See docs/google-calendar.md"

gcal-test: ## Test Google Calendar connection
	@gcalcli list 2>/dev/null && echo "Google Calendar connected!" || echo "Not connected. Run 'gcalcli list' to authenticate."

csv-check: ## Analyze CSV data files and show statistics
	@python3 $(LIFE_OS)/scripts/check_csv_data.py
