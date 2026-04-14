---
name: maestro-e2e
description: Maestro E2E test infrastructure details — dev environment scripts, prerequisites, and troubleshooting for mobile E2E tests.
---

# Maestro E2E Test Infrastructure

Detailed reference for the dev environment and E2E test scripts used by `make e2e-*`.

## When to Activate

- Debugging E2E test failures or environment issues
- Setting up Maestro CLI or dev environment for the first time
- Investigating port conflicts or rogue Maestro processes
- Understanding what `run-dev.sh` or `run-e2e.sh` does internally

## Prerequisites

- **Maestro CLI**: `curl -Ls "https://get.maestro.mobile.dev" | bash`
- Dev environment is started automatically by `make e2e-*` (no need to run `make dev-*` separately)

## Script Responsibilities

### `run-dev.sh` (started via `make dev-ios` / `make dev-android`)

1. Starts Docker (Postgres + Redis) if not running
2. Starts backend API (`uvicorn`) if not running
3. Starts Metro bundler if not running
4. Boots iOS Simulator / Android Emulator as needed
5. Builds and installs the app
6. Keeps Metro in foreground (or returns immediately with `--background`)
7. Cleans up all processes on Ctrl+C (foreground mode only)

### `run-e2e.sh` (started via `make e2e-ios` / `make e2e-android`)

1. Ensures dev environment is running (delegates to `run-dev.sh --background`)
2. Sweeps rogue Maestro processes to avoid port conflicts
3. Runs Maestro test flows with retry on failure

## Troubleshooting

- **Port conflict on 7001**: Check for rogue Maestro processes — `run-e2e.sh` sweeps these automatically, but manual `maestro test` runs can leave orphans
- **Metro serving stale code**: Ensure `make e2e-*` is run from the worktree root, not the main repo
- **Simulator/Emulator not booting**: `run-dev.sh` handles boot automatically; check Xcode / Android Studio setup if it fails
