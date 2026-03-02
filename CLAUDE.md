# Coto — Project Instructions

## OpenAPI TypeScript Type Generation

When backend API schemas change (Pydantic models in `apps/api/src/coto/schemas/`), you MUST regenerate the mobile TypeScript types to keep them in sync.

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

```bash
make e2e           # All flows on both iOS and Android (sequential)
make e2e-ios       # All flows on iOS Simulator only
make e2e-android   # All flows on Android Emulator only

# Single flow (useful for debugging or iterating on one test)
make e2e-ios FLOW=app-launch.yaml
make e2e-android FLOW=navigate-to-history.yaml
```

### Prerequisites

- **Maestro CLI**: `curl -Ls "https://get.maestro.mobile.dev" | bash`
- **iOS**: Boot a simulator — `xcrun simctl boot "iPhone 16 Pro"`
- **Android**: Start an emulator from Android Studio or `emulator -avd <name>`
- **Docker**: Required for Postgres + Redis (`docker compose up -d`)
- **Backend venv**: `apps/api/.venv` must exist with dependencies installed

### What the script does automatically

1. Sweeps rogue Maestro/Metro processes from previous runs or manual invocations
2. Starts Docker (Postgres + Redis) if not running
3. Runs database migrations
4. Starts backend API (`uvicorn`) if not running — stops it on exit
5. Builds and installs the app on the target device
6. Starts Metro and waits for JS bundle compilation to complete before launching the app
7. Runs all Maestro test flows
8. Cleans up Metro and backend on exit (including Ctrl+C / kill)

### Rules

- NEVER use `optional: true` on assertions that validate API responses — E2E tests must verify real backend interactions
- The `run-e2e.sh` script ensures the backend is running; do NOT skip this by running `maestro test` directly
- NEVER run Maestro CLI commands manually (`maestro test`, `maestro hierarchy`, etc.) — rogue Maestro processes cause port conflicts and test failures. Always use `make e2e` / `make e2e-ios` / `make e2e-android` to run E2E tests
- iOS and Android tests run sequentially (Maestro uses port 7001 for both platforms)
- Test flows are in `apps/mobile/e2e/*.yaml`
