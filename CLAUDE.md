# Coyo — Project Instructions

## OpenAPI TypeScript Type Generation

When backend API schemas change (Pydantic models in `apps/api/src/coyo/schemas/`), you MUST regenerate the mobile TypeScript types to keep them in sync.

### Workflow

1. **Export OpenAPI spec** from FastAPI:
   ```bash
   cd apps/api && .venv/bin/python scripts/export_openapi.py openapi.json
   ```

2. **Generate TypeScript types** from the spec:
   ```bash
   cd apps/mobile && npx openapi-typescript ../api/openapi.json -o src/types/generated/api.ts
   ```

3. **Or use the combined Makefile target**:
   ```bash
   make generate-api-types
   ```

4. **Verify** TypeScript compiles:
   ```bash
   cd apps/mobile && npx tsc --noEmit
   ```

### File Structure

- `apps/api/scripts/export_openapi.py` — Extracts OpenAPI JSON from FastAPI app
- `apps/api/openapi.json` — Intermediate file (gitignored)
- `apps/mobile/src/types/generated/api.ts` — Auto-generated types (DO NOT edit manually)
- `apps/mobile/src/types/conversation.ts` — Re-exports from generated types with union literal narrowing
- `apps/mobile/src/types/api.ts` — Client-side types (ApiResponse envelope, SSE TurnEvent) not in OpenAPI

### Rules

- NEVER edit `src/types/generated/api.ts` by hand — it will be overwritten
- When adding/changing API endpoints or response schemas, always run `make generate-api-types`
- SSE event types (`TurnEvent`) are maintained manually in `src/types/api.ts` because SSE is not modelled by OpenAPI
- Screen files should import types from `@/types/conversation` (not define local interfaces)

## E2E Tests (Maestro)

### Running E2E Tests

E2E tests require the dev environment running in a separate terminal.

```bash
# Step 1: Start dev environment (in terminal 1)
make dev-ios       # or: make dev-android / make dev-both

# Step 2: Run E2E tests (in terminal 2)
make e2e-ios       # All flows on iOS Simulator
make e2e-android   # All flows on Android Emulator
make e2e           # All flows on both platforms (sequential)

# Single flow (useful for debugging or iterating on one test)
make e2e-ios FLOW=app-launch.yaml
make e2e-android FLOW=navigate-to-history.yaml
```

### Prerequisites

- **Dev environment running**: `make dev-ios` / `make dev-android` (handles Docker, backend, Metro, device boot, and app build)
- **Maestro CLI**: `curl -Ls "https://get.maestro.mobile.dev" | bash`

### Script responsibilities

**`run-dev.sh`** (started via `make dev-ios` / `make dev-android`):
1. Starts Docker (Postgres + Redis)
2. Starts backend API (`uvicorn`)
3. Boots iOS Simulator / Android Emulator
4. Builds and installs the app
5. Starts Metro bundler (foreground)
6. Cleans up all processes on Ctrl+C

**`run-e2e.sh`** (started via `make e2e-ios` / `make e2e-android`):
1. Validates dev environment is running (API, Metro, device, app)
2. Sweeps rogue Maestro processes to avoid port conflicts
3. Runs Maestro test flows with retry on failure

### Rules

- NEVER use `optional: true` on assertions that validate API responses — E2E tests must verify real backend interactions
- NEVER run Maestro CLI commands manually (`maestro test`, `maestro hierarchy`, etc.) — rogue Maestro processes cause port conflicts and test failures. Always use `make e2e` / `make e2e-ios` / `make e2e-android` to run E2E tests
- NEVER run `maestro test` directly without `make e2e-*` — the script validates the environment and handles cleanup
- iOS and Android tests run sequentially (Maestro uses port 7001 for both platforms)
- Test flows are in `apps/mobile/e2e/*.yaml`
