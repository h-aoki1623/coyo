# Runbook

## Infrastructure

### Local services

| Service | Container | Port | Health check |
|---|---|---|---|
| PostgreSQL 16 | `coto-postgres` | 5432 | `pg_isready -U coto -d coto` |
| Redis 7 | `coto-redis` | 6379 | `redis-cli ping` |

### Start / Stop / Reset

```bash
make docker-up      # Start Postgres + Redis
make docker-down    # Stop containers (data preserved)
make docker-reset   # Destroy volumes and restart (full data wipe)
```

### Verify infrastructure health

```bash
docker compose ps                                          # Container status
docker compose exec postgres pg_isready -U coto -d coto   # Postgres health
docker compose exec redis redis-cli ping                   # Redis health
```

## Deployment

> **Note**: Production deployment procedures are not yet defined. This section covers local development only.

### Backend

```bash
cd apps/api
source .venv/bin/activate
make -C ../.. migrate                                   # Apply pending migrations
uvicorn src.coto.main:app --reload --host 0.0.0.0      # Start dev server
```

### Mobile

```bash
cd apps/mobile
npx expo start --dev-client    # Development
npx expo export                # Verify JS bundle builds (CI validation)
```

## Database Operations

### Run migrations

```bash
make migrate                      # Apply all pending migrations
```

### Create a new migration

```bash
make migrate-new MSG="add users table"   # Auto-generate from model changes
```

### Check migration status

```bash
cd apps/api && .venv/bin/alembic current    # Current revision
cd apps/api && .venv/bin/alembic history    # Migration history
```

### Reset database

```bash
make docker-reset   # Destroys all data and recreates containers
make migrate        # Re-apply all migrations from scratch
```

## Common Issues and Fixes

### Port conflicts

**Symptom**: `address already in use` for ports 5432, 6379, or 8000.

```bash
# Find process using the port
lsof -i :5432   # Postgres
lsof -i :6379   # Redis
lsof -i :8000   # Backend

# Kill the process
kill -9 <PID>
```

### Docker containers not starting

```bash
docker compose down -v   # Clean shutdown
docker compose up -d     # Fresh start
```

### Stale Metro bundler

**Symptom**: Mobile app shows old code or fails to connect.

```bash
# Kill rogue Metro processes
pkill -f "expo start" || true
pkill -f "react-native" || true

# Restart
cd apps/mobile && npx expo start --dev-client --clear
```

### Maestro E2E test failures

**Symptom**: Tests fail with port conflicts or stale processes.

```bash
# The run-e2e.sh script sweeps rogue processes automatically.
# If issues persist:
pkill -f maestro || true
pkill -f "expo start" || true
pkill -f uvicorn || true

# Then retry
make e2e-ios
```

**Android-specific**: `adb reverse` gets cleared when the APK is reinstalled. The `run-e2e.sh` script handles this automatically.

### Database migration conflicts

**Symptom**: `alembic upgrade head` fails with revision errors.

```bash
# Check current state
cd apps/api && .venv/bin/alembic current

# If DB is ahead of code (rare), stamp to match
cd apps/api && .venv/bin/alembic stamp head

# Nuclear option: reset everything
make docker-reset && make migrate
```

### Python venv issues

**Symptom**: Module not found or wrong Python version.

```bash
cd apps/api
rm -rf .venv
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### TypeScript type mismatches

**Symptom**: Mobile app has type errors after backend API changes.

```bash
make generate-api-types              # Regenerate types from OpenAPI spec
cd apps/mobile && npx tsc --noEmit   # Verify
```

## Monitoring (Development)

### Backend logs

```bash
# Structured logs via structlog
make dev-api   # Logs appear in terminal (uvicorn --reload)
```

### Database queries

```bash
# Connect to local Postgres
docker compose exec postgres psql -U coto -d coto

# Useful queries
\dt                          -- List tables
\d+ table_name               -- Table schema
SELECT count(*) FROM turns;  -- Check data
```

### Redis inspection

```bash
docker compose exec redis redis-cli
KEYS *        # List all keys
TTL key_name  # Check TTL
```
