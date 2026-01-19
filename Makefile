.PHONY: help dev-up dev-down dev-restart dev-logs dev-shell bootstrap clean

help:
	@echo "NRG Gyms Home Assistant Integration - Development"
	@echo ""
	@echo "Available commands:"
	@echo "  make bootstrap       - Create config directory and example files"
	@echo "  make dev-up          - Start Home Assistant container"
	@echo "  make dev-down        - Stop Home Assistant container"
	@echo "  make dev-restart     - Restart Home Assistant container"
	@echo "  make dev-logs        - Tail container logs"
	@echo "  make dev-shell       - Open shell in running container"
	@echo "  make clean           - Remove config volume (WARNING: data loss)"
	@echo ""

bootstrap:
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
	@echo "✓ Bootstrap complete. Run 'make dev-up' to start."

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
