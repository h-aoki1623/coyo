# Coto

AI English conversation practice app.

## Project Structure

```
coto/
├── apps/
│   ├── mobile/          # React Native (Expo) app
│   └── api/             # FastAPI backend
├── docs/
│   ├── CONTRIB.md       # Development workflow & scripts reference
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
- Node.js 20+
- Docker (Docker Desktop, OrbStack, or Colima)

### 1. Start Infrastructure

```bash
make docker-up          # Start Postgres + Redis
```

### 2. Backend

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp ../../.env.example .env  # Edit OPENAI_API_KEY with your real key
make -C ../.. migrate       # Run database migrations
uvicorn src.coto.main:app --reload
```

### 3. Mobile

```bash
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

For the full scripts reference, see [docs/CONTRIB.md](docs/CONTRIB.md). For troubleshooting, see [docs/RUNBOOK.md](docs/RUNBOOK.md).
