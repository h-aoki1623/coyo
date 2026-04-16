.PHONY: dev-mobile dev-api dev-ios dev-android dev-both dev-stop lint lint-mobile lint-api test test-mobile test-api e2e e2e-ios e2e-android migrate migrate-new docker-up docker-down docker-reset generate-api-types db-clean-users eval-a eval-b eval-c eval-all api-lock api-install api-test api-cmd

# Python dependency management (uv-based, with release-age cooldown)
#
# api-install   Install API dependencies from uv.lock into apps/api/.venv.
#               Use this for environment setup. No network resolution: deps
#               are restored verbatim from the lockfile, so the supply-chain
#               cooldown that was applied at lock time is preserved.
#
# api-test      Run pytest via uv run --frozen (lockfile is never re-resolved).
#               Pass extra args: make api-test ARGS="-k test_foo -v"
#
# api-cmd       Run an arbitrary command via uv run --frozen.
#               Example: make api-cmd CMD="ruff check src/"
#
# api-lock      Regenerate apps/api/uv.lock with the cooldown applied
#               (versions younger than UV_COOLDOWN_DAYS days are excluded).
#               Use this whenever you add, remove, or upgrade a dependency.
#
# Why two targets:
#   - install is fast and deterministic; lock is slow and rewrites uv.lock
#   - the supply-chain cooldown only matters at lock time
#
# Both targets are the only sanctioned way for humans (and Claude Code) to
# touch uv. The .claude/hooks/check-uv-install.sh hook (PR2) will block any
# direct `uv pip install` / `uv lock` / `pip install` invocation.
api-lock:
	cd apps/api && ../../scripts/uv-install.sh lock

api-test:
	cd apps/api && uv run --frozen --extra dev pytest $(ARGS)

api-cmd:
	@if [ -z "$(CMD)" ]; then echo "ERROR: CMD is required. Usage: make api-cmd CMD=\"ruff check src/\""; exit 1; fi
	cd apps/api && uv run --frozen --extra dev $(CMD)

api-install:
	@if [ apps/api/pyproject.toml -nt apps/api/uv.lock ]; then \
	  echo "ERROR: apps/api/pyproject.toml is newer than apps/api/uv.lock"; \
	  echo "       Run 'make api-lock' first to regenerate the lockfile with the cooldown."; \
	  exit 1; \
	fi
	cd apps/api && uv sync --frozen --extra dev

# Infrastructure
docker-up:
	docker compose up -d
	@echo "Waiting for Postgres to be ready..."
	@docker compose exec postgres pg_isready -U coyo -d coyo > /dev/null 2>&1 || sleep 3
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
	cd apps/api && .venv/bin/uvicorn src.coyo.main:app --reload

# Full dev environment (Docker + API + Emulator + Build + Metro)
dev-ios:
	cd apps/mobile && ./run-dev.sh ios

dev-android:
	cd apps/mobile && ./run-dev.sh android

dev-both:
	cd apps/mobile && ./run-dev.sh both

dev-stop:
	./scripts/stop-dev.sh

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
# Requires: dev environment running in another terminal (make dev-ios / make dev-android)
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

# Cleanup (development only)
db-clean-users:
	@echo "Deleting all users from the local database..."
	docker compose exec postgres psql -U coyo -d coyo -c "DELETE FROM users;"
	@echo "Done. Remember to also delete users in Firebase Console."

# Evaluation
eval-a:
	cd apps/api && .venv/bin/python -m eval run-a

eval-b:
	cd apps/api && .venv/bin/python -m eval run-b

eval-c:
	cd apps/api && .venv/bin/python -m eval run-c

eval-all:
	cd apps/api && .venv/bin/python -m eval run-all

# OpenAPI TypeScript type generation
generate-api-types:
	cd apps/api && .venv/bin/python scripts/export_openapi.py openapi.json
	cd apps/mobile && npx openapi-typescript ../api/openapi.json -o src/types/generated/api.ts
