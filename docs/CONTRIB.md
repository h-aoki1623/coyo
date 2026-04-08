# Contributing to Coyo

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`) — Python package manager
- Node.js 20+
- **npm >= 11.10.0** (`npm install -g npm@11.10.0`) — required for the `min-release-age` supply-chain cooldown in `apps/mobile/.npmrc`
- Docker (Docker Desktop, OrbStack, or Colima)
- Maestro CLI (for E2E tests): `curl -Ls "https://get.maestro.mobile.dev" | bash`

## Supply-chain defense (MUST)

To reduce exposure to malicious package releases (e.g., the 2025 axios hijack),
this repo enforces a **release-age cooldown** on new dependencies:

- **Python**: `apps/api/uv.lock` is generated with a 7-day cooldown via
  `scripts/uv-install.sh`. Never run `uv pip install` / `uv add` / `uv lock`
  directly — use the Makefile targets instead:
  - `make api-lock`    — regenerate `uv.lock` (use when adding / upgrading deps)
  - `make api-install` — install deps from the lockfile into `apps/api/.venv`
- **JavaScript / Mobile**: `apps/mobile/.npmrc` sets `min-release-age=7d`.
  `npm install` / `npm ci` will refuse to install packages younger than 7 days.
  This requires npm >= 11.10.0 (see Prerequisites above).

A pre-commit / Claude Code hook will be added in a follow-up PR to block any
direct bypass of these guardrails.

## Environment Setup

### 1. Clone and configure environment

```bash
cp .env.example apps/api/.env
# Edit apps/api/.env — set OPENAI_API_KEY to your real key
```

### 2. Start infrastructure

```bash
make docker-up    # Postgres 16 + Redis 7 via Docker Compose
```

### 3. Backend (FastAPI)

```bash
make api-install        # uv sync --frozen from apps/api/uv.lock (with dev extras)
make migrate            # Run database migrations
```

To add, remove, or upgrade a Python dependency:

```bash
# 1. Edit apps/api/pyproject.toml
# 2. Regenerate the lockfile (applies the 7-day cooldown)
make api-lock
# 3. Re-sync your venv to pick up the new versions
make api-install
# 4. Commit both pyproject.toml AND uv.lock
```

### 4. Mobile (React Native / Expo)

```bash
cd apps/mobile
npm install
```

## Environment Variables

Source: `.env.example`

| Variable | Purpose | Example |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string (async driver) | `postgresql+asyncpg://coyo:coyo_local@localhost:5432/coyo` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379` |
| `OPENAI_API_KEY` | OpenAI API key for conversation AI | `sk-xxx` |
| `GCS_BUCKET_NAME` | Google Cloud Storage bucket for audio files | `coyo-audio-dev` |
| `API_BASE_URL` | Backend URL for mobile app | `http://localhost:8000` |
| `APP_ENV` | App environment identifier | `development` |

## Development Workflow

### Starting the dev environment

```bash
# Full stack (Docker + API + Simulator + Metro) — recommended
make dev-ios          # iOS Simulator
make dev-android      # Android Emulator
make dev-both         # Both platforms

# Individual services
make dev-api          # Backend only (uvicorn --reload)
make dev-mobile       # Expo dev server only
```

### API type generation

When backend API schemas change, regenerate mobile TypeScript types:

```bash
make generate-api-types
```

This exports the OpenAPI spec from FastAPI and generates `apps/mobile/src/types/generated/api.ts`.

## Available Scripts

### Root Makefile

| Command | Description |
|---|---|
| `make docker-up` | Start Postgres + Redis containers |
| `make docker-down` | Stop containers |
| `make docker-reset` | Destroy volumes and restart (full DB reset) |
| `make dev-api` | Start backend dev server (uvicorn --reload) |
| `make dev-mobile` | Start Expo dev server |
| `make dev-ios` | Full dev environment for iOS |
| `make dev-android` | Full dev environment for Android |
| `make dev-both` | Full dev environment for both platforms |
| `make lint` | Lint both apps |
| `make lint-mobile` | Lint mobile app (ESLint) |
| `make lint-api` | Lint backend (Ruff) |
| `make test` | Run all tests |
| `make test-mobile` | Run mobile tests (Jest) |
| `make test-api` | Run backend tests (pytest) |
| `make e2e` | Run all E2E flows on both platforms |
| `make e2e-ios` | Run E2E flows on iOS Simulator |
| `make e2e-android` | Run E2E flows on Android Emulator |
| `make e2e-ios FLOW=<file>` | Run single E2E flow on iOS |
| `make e2e-android FLOW=<file>` | Run single E2E flow on Android |
| `make migrate` | Run database migrations (Alembic) |
| `make migrate-new MSG="desc"` | Create a new migration |
| `make generate-api-types` | Export OpenAPI spec and generate TS types |

### Mobile (`apps/mobile/package.json`)

| Script | Description |
|---|---|
| `npm start` | Start Expo dev server (`--dev-client`) |
| `npm run android` | Build and run on Android Emulator |
| `npm run ios` | Build and run on iOS Simulator |
| `npm run lint` | Run ESLint on `src/` |
| `npm test` | Run Jest tests |
| `npm run typecheck` | TypeScript type checking (`tsc --noEmit`) |
| `npm run postinstall` | Apply patches via `patch-package` |

### Backend (`apps/api/pyproject.toml`)

| Tool | Command | Description |
|---|---|---|
| pytest | `.venv/bin/pytest` | Run tests (async mode auto) |
| ruff | `.venv/bin/ruff check src/` | Lint Python code |
| mypy | `.venv/bin/mypy src/` | Static type checking (strict) |
| alembic | `.venv/bin/alembic upgrade head` | Run migrations |

## Testing

### Unit and integration tests

```bash
make test          # Both apps
make test-mobile   # Jest (apps/mobile)
make test-api      # pytest (apps/api)
```

### E2E tests (Maestro)

```bash
make e2e-ios                          # All flows on iOS
make e2e-android                      # All flows on Android
make e2e-ios FLOW=app-launch.yaml     # Single flow
```

The `run-e2e.sh` script handles all setup automatically:
- Starts Docker, runs migrations, starts backend
- Builds and installs the app
- Runs Maestro test flows
- Cleans up on exit

**Important**: Always use `make e2e-*` commands. Never run `maestro test` directly.

## Code Quality

### Linting

- **Mobile**: ESLint with TypeScript plugin
- **Backend**: Ruff (pycodestyle, pyflakes, isort, pyupgrade, bugbear, simplify)

### Type checking

- **Mobile**: TypeScript strict mode (`tsc --noEmit`)
- **Backend**: mypy strict mode with Pydantic plugin

### Formatting

- **Backend**: Ruff (line length: 99, target: Python 3.12)
