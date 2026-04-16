# Coyo

Coyo is an AI-powered English conversation practice app designed to help you improve your English naturally and enjoyably.

### Features

- **Real-time correction** — Coyo reviews your messages and offers natural, constructive feedback to help you refine your grammar, vocabulary, and expression.
- **Personalized conversations** — Conversations adapt to your interests and past episodes, so every session feels relevant and engaging rather than generic.
- **Topic suggestions** — Not sure what to talk about? Coyo surfaces topics tailored to what you care about, so you always have a great starting point.

### Why Coyo?

Language learning sticks when it's personal. Coyo remembers what you've talked about, learns what interests you, and builds on that context to make each conversation more meaningful than the last.

## Project Structure

```
coyo/
├── apps/
│   ├── mobile/          # React Native (Expo) app
│   └── api/             # FastAPI backend
├── docs/
│   ├── CONTRIB.md       # Development workflow & scripts reference
│   ├── DEPLOY.md        # Production deployment guide
│   └── RUNBOOK.md       # Operations, troubleshooting & common fixes
├── docker-compose.yml   # Local Postgres + Redis
├── Makefile             # Root-level task runner
├── .env.example         # Environment variable template
└── README.md
```

## Getting Started

### Platform Support

| Platform | Min Version | Target Version | Coverage |
|---|---|---|---|
| iOS | 16.0 | 18 | ~98% |
| Android | API 29 (Android 10) | API 35 (Android 15) | ~90% |

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Node.js 20+
- npm >= 11.10.0 (`npm install -g npm@11.10.0`) — required for the supply-chain cooldown set in `apps/mobile/.npmrc`
- Docker (Docker Desktop, OrbStack, or Colima)

### 1. Start Infrastructure

```bash
make docker-up          # Start Postgres + Redis
```

### 2. Backend

```bash
cp apps/api/.env.example apps/api/.env  # Edit OPENAI_API_KEY with your real key
make api-install        # uv sync --frozen from apps/api/uv.lock
make migrate            # Run database migrations
make dev-api            # uvicorn --reload
```

When adding, removing, or upgrading a Python dependency:

```bash
# Edit apps/api/pyproject.toml, then regenerate the lockfile with the
# supply-chain cooldown applied, and re-sync your venv.
make api-lock
make api-install
```

### 3. Mobile

```bash
# One-time: upgrade npm so the min-release-age cooldown in apps/mobile/.npmrc
# is honored. engine-strict=true makes `npm install` hard-fail on older npm.
npm install -g npm@11.10.0

cd apps/mobile
npm install
npx expo start --dev-client
```

### Common Commands

```bash
# Infrastructure
make docker-up          # Start Postgres + Redis
make docker-down        # Stop containers
make docker-reset       # Reset DB (destroy volumes and restart)

# Development
make dev-api            # Start backend dev server
make dev-mobile         # Start Expo dev server
make dev-ios            # Full dev environment (Docker + API + iOS Simulator)
make dev-android        # Full dev environment (Docker + API + Android Emulator)

# Quality
make lint               # Lint both apps
make test               # Test both apps
make e2e-ios            # E2E tests on iOS Simulator
make e2e-android        # E2E tests on Android Emulator

# Database
make migrate            # Run migrations
make migrate-new MSG="description"  # Create new migration

# Code generation
make generate-api-types # Regenerate TS types from OpenAPI spec
```

For the full scripts reference, see [docs/CONTRIB.md](docs/CONTRIB.md). For troubleshooting, see [docs/RUNBOOK.md](docs/RUNBOOK.md). For production deployment, see [docs/deploy/DEPLOY.md](docs/deploy/DEPLOY.md).
