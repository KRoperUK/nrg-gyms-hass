
# Python Virtual Environment
VENV_NAME ?= .venv
SHELL := /bin/bash
PYTHON := python3
VENV_ACTIVATE = . $(VENV_NAME)/bin/activate

.PHONY: help dev-up dev-down dev-restart dev-logs dev-shell bootstrap clean venv ci-lint pytest pytest-live

help:
	@echo "NRG Gyms Home Assistant Integration - Development"
	@echo ""
	@echo "Available commands:"
	@echo "  make bootstrap       - Set up development environment (venv, dependencies)"
	@echo "  make dev-up          - Start Home Assistant container"
	@echo "  make dev-down        - Stop Home Assistant container"
	@echo "  make dev-restart     - Restart Home Assistant container"
	@echo "  make dev-logs        - Tail container logs"
	@echo "  make dev-shell       - Open shell in running container"
	@echo "  make clean           - Remove config volume (WARNING: data loss)"
	@echo "  make venv            - Create and update virtual environment"
	@echo "  make ci-lint         - Run linting (black, isort, mypy)"
	@echo "  make pytest          - Run unit tests (skips live tests)"
	@echo "  make pytest-live     - Run all tests including live tests (requires .env)"
	@echo ""

venv:
	@echo "Creating venv..."
	@rm -rf $(VENV_NAME)
	@PYTHON_EXE="$(PYTHON)"; \
	if [ -f .python-version ]; then \
		VER=$$(cat .python-version); \
		CANDIDATE=$$(ls -d $(HOME)/.pyenv/versions/$$VER*/bin/python3 2>/dev/null | head -n 1); \
		if [ -n "$$CANDIDATE" ] && [ -x "$$CANDIDATE" ]; then \
			PYTHON_EXE="$$CANDIDATE"; \
		fi; \
	fi; \
	echo "Using python: $$PYTHON_EXE"; \
	"$$PYTHON_EXE" -m venv $(VENV_NAME)
	@$(VENV_ACTIVATE) && pip install --upgrade pip
	@$(VENV_ACTIVATE) && pip install -r requirements-dev.txt
	@echo "✓ Virtual environment ready (source $(VENV_NAME)/bin/activate)"

bootstrap: venv
	@echo "Setting up development environment..."
	@mkdir -p example-config example-config/custom_components
	@if [ ! -f example-config/configuration.yaml ]; then \
		echo "Creating example configuration.yaml..."; \
		echo "# NRG Gyms Integration Example Configuration" > example-config/configuration.yaml; \
		echo "homeassistant:" >> example-config/configuration.yaml; \
		echo "  name: NRG Gyms Dev" >> example-config/configuration.yaml; \
		echo "  latitude: 53.4" >> example-config/configuration.yaml; \
		echo "  longitude: -2.2" >> example-config/configuration.yaml; \
		echo "  elevation: 0" >> example-config/configuration.yaml; \
		echo "  unit_system: metric" >> example-config/configuration.yaml; \
		echo "  time_zone: Europe/London" >> example-config/configuration.yaml; \
		echo "" >> example-config/configuration.yaml; \
		echo "logger:" >> example-config/configuration.yaml; \
		echo "  default: info" >> example-config/configuration.yaml; \
		echo "  logs:" >> example-config/configuration.yaml; \
		echo "    custom_components.nrg_gyms: debug" >> example-config/configuration.yaml; \
		echo "" >> example-config/configuration.yaml; \
		echo "# NRG Gyms Integration" >> example-config/configuration.yaml; \
		echo "# Add via UI: Settings > Devices & Services > Create Integration" >> example-config/configuration.yaml; \
	fi
	@ln -sf ../custom_components example-config/custom_components 2>/dev/null || true
	@echo "✓ Bootstrap complete. Run 'make dev-up' to start HA container."

dev-up:
	@echo "Starting Home Assistant..."
	docker compose -f dev.compose.yml up -d
	@echo "✓ Home Assistant starting at http://localhost:8123"

dev-down:
	@echo "Stopping Home Assistant..."
	docker compose -f dev.compose.yml down
	@echo "✓ Home Assistant stopped"

dev-restart: dev-down dev-up
	@echo "✓ Home Assistant restarted"

dev-logs:
	@docker compose -f dev.compose.yml logs -f homeassistant

dev-shell:
	@docker compose -f dev.compose.yml exec homeassistant bash

clean:
	@echo "WARNING: This will delete all Home Assistant config and data!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker compose -f dev.compose.yml down -v; \
		rm -rf config; \
		echo "✓ Cleaned"; \
	else \
		echo "Cancelled"; \
	fi

ci-lint:
	@$(VENV_ACTIVATE) && echo "Running Black..." && black --check .
	@$(VENV_ACTIVATE) && echo "Running Isort..." && isort --check-only .
	@$(VENV_ACTIVATE) && echo "Running Mypy..." && mypy .

pytest:
	@$(VENV_ACTIVATE) && pytest -v -m "not live"

pytest-live:
	@if [ -f .env ]; then \
		export $$(cat .env | xargs) && $(VENV_ACTIVATE) && pytest -v; \
	else \
		echo "Error: .env file not found. Create one from .env.example to run live tests."; \
		exit 1; \
	fi

# Alias for pytest-live with colon
pytest\:live: pytest-live
