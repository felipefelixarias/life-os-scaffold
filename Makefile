.PHONY: help setup test lint clean gcal-agenda gcal-test csv-check deps-check health refresh-examples dev-setup format security type-check dev-install pre-commit-install

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

deps-check: ## Check Python dependencies and security status
	@python3 $(LIFE_OS)/scripts/check_dependencies.py

health: ## Comprehensive repository health check
	@python3 $(LIFE_OS)/scripts/repo_health.py

refresh-examples: ## Refresh CSV files with fresh example data
	@python3 $(LIFE_OS)/scripts/refresh_example_data.py

dev-check: ## Run all development checks (test, lint, csv, health)
	@echo "Running comprehensive development checks..."
	@$(MAKE) test
	@$(MAKE) lint
	@$(MAKE) csv-check
	@$(MAKE) health
	@echo "✅ All development checks passed!"

dev-setup: ## Set up development environment with all tools
	@echo "Setting up development environment..."
	@python3 -m venv venv || echo "Virtual environment already exists"
	@source venv/bin/activate && pip install --upgrade pip
	@source venv/bin/activate && pip install -r requirements.txt
	@source venv/bin/activate && pip install -r requirements-dev.txt
	@echo "✅ Development environment setup complete!"

dev-install: ## Install package in development mode
	@source venv/bin/activate && pip install -e .

pre-commit-install: ## Install pre-commit hooks
	@source venv/bin/activate && pre-commit install
	@echo "✅ Pre-commit hooks installed!"

format: ## Format code with black and isort
	@source venv/bin/activate && black .
	@source venv/bin/activate && isort .
	@echo "✅ Code formatted!"

security: ## Run security checks with bandit and safety
	@echo "Running security checks..."
	@source venv/bin/activate && bandit -r 01-ops/life-os/scripts/ || echo "⚠️  Security issues found"
	@source venv/bin/activate && safety check || echo "⚠️  Vulnerability scan completed with warnings"

type-check: ## Run type checking with mypy
	@source venv/bin/activate && mypy 01-ops/life-os/scripts/ || echo "⚠️  Type checking completed with issues"

quality: ## Run all quality checks (format, security, type-check, lint)
	@echo "Running comprehensive quality checks..."
	@$(MAKE) format
	@$(MAKE) security
	@$(MAKE) type-check
	@$(MAKE) lint
	@echo "✅ Quality checks completed!"
