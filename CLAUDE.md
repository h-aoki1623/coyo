# Coyo — Project Instructions

## Workflow Compliance (MUST)

Before starting ANY task, Claude MUST follow these steps in order. No steps may be skipped regardless of task size or perceived simplicity.

1. **Classify** the task type (Feature / Bugfix / Refactor / DB Change / Docs) per `.claude/rules/common/workflow.md`
2. **Look up** the required agents and phases for that workflow type in `workflow.md`
3. **Create a task checklist** listing every required agent and verification step before writing any code
4. **Execute each step** using the designated agent — never perform an agent's job directly
5. **Verify gate conditions** are met before proceeding to the next phase (see workflow.md for gate conditions)

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

```bash
make e2e-ios       # All flows on iOS Simulator
make e2e-android   # All flows on Android Emulator
make e2e           # All flows on both platforms (sequential)

# Single flow (useful for debugging or iterating on one test)
make e2e-ios FLOW=app-launch.yaml
make e2e-android FLOW=navigate-to-history.yaml
```

### Prerequisites

- **Maestro CLI**: `curl -Ls "https://get.maestro.mobile.dev" | bash`
- Dev environment is started automatically by `make e2e-*` (no need to run `make dev-*` separately)

### Script responsibilities

**`run-dev.sh`** (started via `make dev-ios` / `make dev-android`):
1. Starts Docker (Postgres + Redis) if not running
2. Starts backend API (`uvicorn`) if not running
3. Starts Metro bundler if not running
4. Boots iOS Simulator / Android Emulator as needed
5. Builds and installs the app
6. Keeps Metro in foreground (or returns immediately with `--background`)
7. Cleans up all processes on Ctrl+C (foreground mode only)

**`run-e2e.sh`** (started via `make e2e-ios` / `make e2e-android`):
1. Ensures dev environment is running (delegates to `run-dev.sh --background`)
2. Sweeps rogue Maestro processes to avoid port conflicts
3. Runs Maestro test flows with retry on failure

### Rules

- NEVER use `optional: true` on assertions that validate API responses — E2E tests must verify real backend interactions
- NEVER run Maestro CLI commands manually (`maestro test`, `maestro hierarchy`, etc.) — rogue Maestro processes cause port conflicts and test failures. Always use `make e2e` / `make e2e-ios` / `make e2e-android` to run E2E tests
- NEVER run `maestro test` directly without `make e2e-*` — the script validates the environment and handles cleanup
- iOS and Android tests run sequentially (Maestro uses port 7001 for both platforms)
- Test flows are in `apps/mobile/e2e/*.yaml`
- `make e2e-*` commands are auto-backgrounded by the Bash tool (cannot be prevented). After receiving the background completion notification, check the result file to determine pass/fail. Do NOT retry based on exit code alone — always read the result file first.

### Checking E2E Results

`run-e2e.sh` writes a result file after each platform run. Always check this file after E2E completion:

```bash
cat apps/mobile/e2e/results/e2e-result-latest.txt
```

The file contains: `platform`, `status` (PASS/FAIL), `duration`, `timestamp`, and failure `details` if applicable.
