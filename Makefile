.PHONY: setup gcal-agenda gcal-test help

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
