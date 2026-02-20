.PHONY: dev-mobile dev-api lint lint-mobile lint-api test test-mobile test-api migrate migrate-new docker-up docker-down docker-reset

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
	cd apps/api && uvicorn src.coto.main:app --reload

# Linting
lint: lint-mobile lint-api

lint-mobile:
	cd apps/mobile && npx eslint src/

lint-api:
	cd apps/api && ruff check src/

# Testing
test: test-mobile test-api

test-mobile:
	cd apps/mobile && npx jest

test-api:
	cd apps/api && pytest

# Database Migrations
migrate:
	cd apps/api && alembic upgrade head

migrate-new:
	cd apps/api && alembic revision --autogenerate -m "$(MSG)"
