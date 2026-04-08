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
- **JavaScript / Mobile**: `apps/mobile/.npmrc` sets `min-release-age=7` (days).
  `npm install` / `npm ci` will refuse to install packages younger than 7 days.
  This requires npm >= 11.10.0 (see Prerequisites above).

### Claude Code hooks (speed bump, not a security boundary)

For sessions that use Claude Code, two `PreToolUse` hooks (wired in
`.claude/settings.json`) catch **accidental** invocations that would
bypass the cooldown:

- **`.claude/hooks/check-uv-install.sh`** — refuses Bash commands that
  invoke `uv pip install` / `uv pip compile|sync|uninstall`, `uv add`,
  `uv remove`, `uv lock`, `uv sync` (without `--frozen`),
  `uv tool install|run|upgrade`, `uvx`, or `pip install`. Also refuses
  `bash -c '...'` / `sh -c '...'` / `eval '...'` / `python -c '...'` when
  the inner string mentions any of the above. Also refuses Bash file
  mutations (`chmod`, `rm`, `mv`, `cp`, `sed -i`, `tee`, `ln`, `>`/`>>`)
  that target any protected file, so the hook cannot be silently disabled
  by `chmod -x .claude/hooks/check-uv-install.sh`.
- **`.claude/hooks/check-protected-files.sh`** — refuses Edit/Write/MultiEdit
  on the files that enforce the policy: `apps/mobile/.npmrc`,
  `scripts/uv-install.sh`, `scripts/install-npm-pinned.sh`, and the two
  hook scripts themselves. Symlink targets are resolved before matching.

The sanctioned entry points are `make api-lock`, `make api-install`,
`bash scripts/uv-install.sh`, `bash scripts/install-npm-pinned.sh`, and
the no-resolution uv subcommands (`uv venv`, `uv run`, `uv sync --frozen`,
`uv --version`).

> **What these hooks are NOT:** a security boundary against a motivated
> or compromised actor. Regex over a shell command string cannot reliably
> understand variable expansion (`U=uv; $U pip install …`), string
> concatenation, PATH shadowing, aliases, indirect interpreters, or
> "edit `.claude/settings.json` to remove the hook entries". Real
> supply-chain enforcement lives in `apps/api/uv.lock` + `uv sync --frozen`
> everywhere (PR1a/1b), `apps/mobile/.npmrc` + `engine-strict=true`
> (PR1b), the SHA-256 integrity check on the hook + wrapper scripts in
> `.security/hook-hashes.sha256` (verified by CI), and code review on
> `.claude/settings.json` changes.

#### Updating a protected file legitimately

To bump the pinned npm version, update the wrapper for a new uv release,
or otherwise edit a protected file or run an off-list uv command for a
one-off task:

1. **Disable the hook for your session** by writing to
   `.claude/settings.local.json` (gitignored, so the override stays on
   your machine and never lands in a commit):
   ```json
   {
     "hooks": {
       "PreToolUse": []
     }
   }
   ```
2. **Make the edit / run the command.**
3. **Re-run the smoke tests** to confirm nothing regressed:
   ```bash
   bash scripts/test/test-claude-hooks.sh
   bash scripts/test/test-uv-install.sh
   ```
4. **Regenerate the integrity hashes** if you touched any of the protected
   files (otherwise CI will fail with a hash mismatch):
   ```bash
   sha256sum .claude/hooks/check-uv-install.sh \
             .claude/hooks/check-protected-files.sh \
             scripts/uv-install.sh \
             scripts/install-npm-pinned.sh \
             scripts/test/test-claude-hooks.sh \
             scripts/test/test-uv-install.sh \
       > .security/hook-hashes.sha256
   ```
5. **Revert the local override** by deleting the `PreToolUse` entry from
   `.claude/settings.local.json` (or removing the file entirely).

Both hooks are smoke-tested by `scripts/test/test-claude-hooks.sh` and
the wrapper by `scripts/test/test-uv-install.sh`, both of which run in CI
on every PR. The integrity check (`sha256sum -c .security/hook-hashes.sha256`)
runs in the same CI workflow.

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
