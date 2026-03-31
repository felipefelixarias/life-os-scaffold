.PHONY: setup gcal-agenda gcal-test help validate test integrity-check fix-data clean install-hooks

LIFE_OS := 01-ops/life-os

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: ## Copy example configs and get started
	@test -f $(LIFE_OS)/config/profile.json || (cp $(LIFE_OS)/config/profile.example.json $(LIFE_OS)/config/profile.json && echo "Created profile.json — edit it with your details")
	@test -f $(LIFE_OS)/config/calendar_feeds.json || (cp $(LIFE_OS)/config/calendar_feeds.example.json $(LIFE_OS)/config/calendar_feeds.json && echo "Created calendar_feeds.json — add your calendar URLs")
	@echo "Setup complete. Run 'claude' to start using life-os."

gcal-agenda: ## Show today's Google Calendar agenda
	@gcalcli agenda "$$(date +%Y-%m-%d)" "$$(date -v+1d +%Y-%m-%d)" 2>/dev/null || echo "gcalcli not configured. See docs/google-calendar.md"

gcal-test: ## Test Google Calendar connection
	@gcalcli list 2>/dev/null && echo "Google Calendar connected!" || echo "Not connected. Run 'gcalcli list' to authenticate."

# Data Validation and Testing
validate: ## Run CSV schema validation
	@echo "🔍 Validating CSV schemas..."
	@python3 $(LIFE_OS)/scripts/validate_data.py

test: ## Run all data validation tests
	@echo "🧪 Running validation tests..."
	@python3 $(LIFE_OS)/scripts/test_data_validation.py

integrity-check: ## Run comprehensive data integrity check
	@echo "🔍 Running integrity check..."
	@python3 $(LIFE_OS)/scripts/integrity_checker.py

fix-data: ## Run integrity check with auto-fix enabled
	@echo "🔧 Running integrity check with auto-fix..."
	@python3 $(LIFE_OS)/scripts/integrity_checker.py --fix

full-check: validate integrity-check test ## Run all validation checks and tests
	@echo "✅ Full validation suite completed!"

clean: ## Clean up temporary files and cache
	@echo "🧹 Cleaning up..."
	@find . -name "*.pyc" -delete
	@find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cleanup complete!"

install-hooks: ## Install git hooks for automatic validation
	@echo "🔗 Installing git hooks..."
	@mkdir -p .git/hooks
	@cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
echo "🔍 Running pre-commit validation..."
make validate
if [ $$? -ne 0 ]; then
    echo "❌ Validation failed! Fix issues before committing."
    exit 1
fi
echo "✅ Validation passed!"
EOF
	@chmod +x .git/hooks/pre-commit
	@echo "✅ Pre-commit hook installed!"
