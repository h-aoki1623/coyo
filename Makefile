.PHONY: dev-mobile dev-api dev-ios dev-android dev-both lint lint-mobile lint-api test test-mobile test-api e2e e2e-ios e2e-android migrate migrate-new docker-up docker-down docker-reset generate-api-types

# Infrastructure
docker-up:
	docker compose up -d
	@echo "Waiting for Postgres to be ready..."
	@docker compose exec postgres pg_isready -U coto -d coto > /dev/null 2>&1 || sleep 3
	@echo "Postgres and Redis are running."

docker-down:
	docker compose down

docker-reset:
	docker compose down -v
	docker compose up -d

# Development
dev-mobile:
	cd apps/mobile && npx expo start --dev-client

dev-api:
	cd apps/api && .venv/bin/uvicorn src.coto.main:app --reload

# Full dev environment (Docker + API + Emulator + Build + Metro)
dev-ios:
	cd apps/mobile && ./run-dev.sh ios

dev-android:
	cd apps/mobile && ./run-dev.sh android

dev-both:
	cd apps/mobile && ./run-dev.sh both

# Linting
lint: lint-mobile lint-api

lint-mobile:
	cd apps/mobile && npx eslint src/

lint-api:
	cd apps/api && .venv/bin/ruff check src/

# Testing
test: test-mobile test-api

test-mobile:
	cd apps/mobile && npx jest

test-api:
	cd apps/api && .venv/bin/pytest

# E2E Tests (Maestro)
# Usage:
#   make e2e                              # All flows on both platforms
#   make e2e-ios                          # All flows on iOS
#   make e2e-android                      # All flows on Android
#   make e2e-ios FLOW=app-launch.yaml     # Single flow on iOS
#   make e2e-android FLOW=app-launch.yaml # Single flow on Android
e2e:
	cd apps/mobile && ./e2e/run-e2e.sh all $(FLOW)

e2e-ios:
	cd apps/mobile && ./e2e/run-e2e.sh ios $(FLOW)

e2e-android:
	cd apps/mobile && ./e2e/run-e2e.sh android $(FLOW)

# Database Migrations
migrate:
	cd apps/api && .venv/bin/alembic upgrade head

migrate-new:
	cd apps/api && .venv/bin/alembic revision --autogenerate -m "$(MSG)"

# OpenAPI TypeScript type generation
generate-api-types:
	cd apps/api && .venv/bin/python scripts/export_openapi.py openapi.json
	cd apps/mobile && npx openapi-typescript ../api/openapi.json -o src/types/generated/api.ts
