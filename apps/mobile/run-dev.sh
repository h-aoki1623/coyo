#!/usr/bin/env bash
# run-dev.sh — One-command dev environment setup for iOS / Android / both
#
# Usage:
#   ./run-dev.sh ios          # Boot iOS Simulator, build, and start Metro
#   ./run-dev.sh android      # Start Android Emulator, build, and start Metro
#   ./run-dev.sh both         # Start both platforms
#
# What it does:
#   1. Starts Docker (Postgres + Redis) if not running
#   2. Starts the backend API if not running
#   3. Boots iOS Simulator / starts Android Emulator as needed
#   4. Builds and installs the app
#   5. Sets up adb reverse port forwarding (Android)
#   6. Keeps Metro bundler running in foreground
#   7. On Ctrl+C: cleans up background processes started by this script
#
# Prerequisites:
#   - Node.js / npm / npx
#   - Xcode (for iOS)
#   - Android SDK with an AVD configured (for Android)
#   - Docker Desktop
#   - Python venv at apps/api/.venv

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MOBILE_DIR="$SCRIPT_DIR"
REPO_ROOT="$(cd "$MOBILE_DIR/../.." && pwd)"
# Main repo root (overridden if in a worktree)
_MAIN_REPO_ROOT="$REPO_ROOT"
# Docker Compose project name (consistent across main repo and worktrees)
_COMPOSE_PROJECT="$(basename "$REPO_ROOT")"
API_DIR="$REPO_ROOT/apps/api"

API_PORT=8000
API_HEALTH_URL="http://localhost:${API_PORT}/health"

# Track PIDs for cleanup
_PIDS_TO_KILL=()
_API_STARTED_BY_SCRIPT=false

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[dev]${NC} $*"; }
warn() { echo -e "${YELLOW}[dev]${NC} $*"; }
err()  { echo -e "${RED}[dev]${NC} $*" >&2; }
info() { echo -e "${CYAN}[dev]${NC} $*"; }

# ===========================================================================
# Worktree support
# ===========================================================================

# Detect if running inside a git worktree and symlink node_modules/.venv
# from the main repo so that builds and backend startup work correctly.
ensure_worktree_deps() {
  local main_repo
  main_repo="$(git -C "$REPO_ROOT" worktree list --porcelain | head -1 | sed 's/^worktree //')"

  # Not in a worktree — nothing to do
  if [[ "$main_repo" == "$REPO_ROOT" ]]; then
    return
  fi

  log "Detected worktree. Main repo: $main_repo"
  _MAIN_REPO_ROOT="$main_repo"
  _COMPOSE_PROJECT="$(basename "$main_repo")"

  # Symlink node_modules (remove broken symlinks first)
  if [[ -L "$MOBILE_DIR/node_modules" && ! -d "$MOBILE_DIR/node_modules" ]]; then
    warn "Removing broken node_modules symlink."
    rm "$MOBILE_DIR/node_modules"
  fi
  if [[ ! -d "$MOBILE_DIR/node_modules" && ! -L "$MOBILE_DIR/node_modules" ]]; then
    if [[ ! -d "$main_repo/apps/mobile/node_modules" ]]; then
      err "node_modules not found in main repo. Run: cd $main_repo/apps/mobile && npm install"
      exit 1
    fi
    ln -s "$main_repo/apps/mobile/node_modules" "$MOBILE_DIR/node_modules"
    log "Symlinked node_modules from main repo."
  fi

  # Symlink .venv (remove broken symlinks first)
  if [[ -L "$API_DIR/.venv" && ! -d "$API_DIR/.venv" ]]; then
    warn "Removing broken .venv symlink."
    rm "$API_DIR/.venv"
  fi
  if [[ ! -d "$API_DIR/.venv" && ! -L "$API_DIR/.venv" ]]; then
    if [[ ! -d "$main_repo/apps/api/.venv" ]]; then
      err ".venv not found in main repo. Run: cd $main_repo/apps/api && python3 -m venv .venv"
      exit 1
    fi
    ln -s "$main_repo/apps/api/.venv" "$API_DIR/.venv"
    log "Symlinked .venv from main repo."
  fi

  # Symlink .env (remove broken symlinks first)
  if [[ -L "$API_DIR/.env" && ! -f "$API_DIR/.env" ]]; then
    warn "Removing broken .env symlink."
    rm "$API_DIR/.env"
  fi
  if [[ ! -f "$API_DIR/.env" && ! -L "$API_DIR/.env" ]]; then
    if [[ ! -f "$main_repo/apps/api/.env" ]]; then
      err ".env not found in main repo. Create: $main_repo/apps/api/.env"
      exit 1
    fi
    ln -s "$main_repo/apps/api/.env" "$API_DIR/.env"
    log "Symlinked .env from main repo."
  fi
}

ensure_worktree_deps

# ===========================================================================
# Cleanup
# ===========================================================================

cleanup() {
  echo ""
  log "Shutting down... (exit code: $?)"

  # Kill background processes we started
  if [[ ${#_PIDS_TO_KILL[@]} -gt 0 ]]; then
    for pid in "${_PIDS_TO_KILL[@]}"; do
      if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
      fi
    done
  fi

  # Stop backend if we started it
  if [[ "$_API_STARTED_BY_SCRIPT" == "true" ]]; then
    log "Stopping backend API..."
    local pids
    pids=$(lsof -ti :"$API_PORT" 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
      echo "$pids" | xargs kill 2>/dev/null || true
    fi
  fi

  log "Done. Goodbye!"
}

trap cleanup EXIT INT TERM

# ===========================================================================
# Metro
# ===========================================================================

# Kill any existing Metro process on port 8081
# (e.g. leftover from a previous session, build copy, or expo run:*)
kill_existing_metro() {
  local pids
  pids=$(lsof -ti :8081 2>/dev/null || true)
  if [[ -z "$pids" ]]; then
    return
  fi

  warn "Killing existing Metro process on port 8081 (PIDs: $pids)"
  # Stage 1: graceful SIGTERM
  echo "$pids" | xargs kill 2>/dev/null || true
  sleep 2

  # Stage 2: SIGKILL anything that didn't exit
  local remaining
  remaining=$(lsof -ti :8081 2>/dev/null || true)
  if [[ -n "$remaining" ]]; then
    warn "Metro did not exit after SIGTERM; force-killing (PIDs: $remaining)"
    echo "$remaining" | xargs kill -9 2>/dev/null || true
    sleep 1
  fi
}

# ===========================================================================
# Docker
# ===========================================================================

ensure_docker() {
  if docker info &>/dev/null; then
    log "Docker daemon is running."
  else
    log "Starting Docker Desktop..."
    open -a Docker 2>/dev/null || true
    local retries=30
    while ! docker info &>/dev/null; do
      retries=$((retries - 1))
      if [[ $retries -le 0 ]]; then
        err "Docker did not start within 60 seconds."
        exit 1
      fi
      sleep 2
    done
    log "Docker Desktop started."
  fi

  if docker compose -f "$REPO_ROOT/docker-compose.yml" -p "$_COMPOSE_PROJECT" ps --status running 2>/dev/null | grep -q "postgres"; then
    log "Docker services already running."
  else
    log "Starting Docker services (Postgres + Redis)..."
    docker compose -f "$REPO_ROOT/docker-compose.yml" -p "$_COMPOSE_PROJECT" up -d
    local retries=10
    while ! docker compose -f "$REPO_ROOT/docker-compose.yml" -p "$_COMPOSE_PROJECT" exec -T postgres pg_isready -U coyo -d coyo > /dev/null 2>&1; do
      retries=$((retries - 1))
      if [[ $retries -le 0 ]]; then
        err "Postgres did not become ready."
        exit 1
      fi
      sleep 2
    done
    log "Docker services are running."
  fi
}

# ===========================================================================
# Backend
# ===========================================================================

ensure_backend() {
  if curl -sf --max-time 3 "$API_HEALTH_URL" > /dev/null 2>&1; then
    log "Backend API already running."
    return
  fi

  ensure_docker

  # Verify venv
  if [[ ! -x "$API_DIR/.venv/bin/python" ]]; then
    err "Python venv not found at $API_DIR/.venv"
    err "Create it with: cd $API_DIR && python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'"
    exit 1
  fi

  local venv_python
  venv_python=$("$API_DIR/.venv/bin/python" -c "import sys; print(sys.executable)" 2>/dev/null || true)
  if [[ -z "$venv_python" ]]; then
    err "Python venv is broken. Recreate with: cd $API_DIR && python3 -m venv .venv --clear && .venv/bin/pip install -e '.[dev]'"
    exit 1
  fi

  # Run migrations
  log "Running database migrations..."
  cd "$API_DIR"
  .venv/bin/alembic upgrade head 2>&1 | tail -3

  # Start uvicorn in background
  log "Starting backend API..."
  cd "$API_DIR"
  .venv/bin/uvicorn src.coyo.main:app --port "$API_PORT" &
  local api_pid=$!
  _PIDS_TO_KILL+=("$api_pid")
  _API_STARTED_BY_SCRIPT=true

  local retries=15
  while ! curl -sf --max-time 2 "$API_HEALTH_URL" > /dev/null 2>&1; do
    retries=$((retries - 1))
    if [[ $retries -le 0 ]]; then
      err "Backend API did not start within 30 seconds."
      exit 1
    fi
    sleep 2
  done
  log "Backend API is running (PID: $api_pid)."
}

# ===========================================================================
# iOS Simulator
# ===========================================================================

get_booted_ios_udid() {
  xcrun simctl list devices booted -j 2>/dev/null \
    | python3 -c "
import json, sys
data = json.load(sys.stdin)
for runtime, devices in data.get('devices', {}).items():
    for d in devices:
        if d.get('state') == 'Booted':
            print(d['udid'])
            sys.exit(0)
sys.exit(1)
" 2>/dev/null || true
}

boot_ios_simulator() {
  local udid
  udid=$(get_booted_ios_udid)
  if [[ -n "$udid" ]]; then
    log "iOS Simulator already booted: $udid"
    return
  fi

  # Pick the first available iPhone simulator
  local target_udid
  target_udid=$(xcrun simctl list devices available -j 2>/dev/null \
    | python3 -c "
import json, sys
data = json.load(sys.stdin)
for runtime, devices in sorted(data.get('devices', {}).items(), reverse=True):
    for d in devices:
        if d.get('isAvailable') and 'iPhone' in d.get('name', '') and 'Pro' in d.get('name', ''):
            print(d['udid'])
            sys.exit(0)
# Fallback: any iPhone
for runtime, devices in sorted(data.get('devices', {}).items(), reverse=True):
    for d in devices:
        if d.get('isAvailable') and 'iPhone' in d.get('name', ''):
            print(d['udid'])
            sys.exit(0)
sys.exit(1)
" 2>/dev/null) || true

  if [[ -z "$target_udid" ]]; then
    err "No iPhone simulator found. Create one in Xcode > Window > Devices and Simulators."
    exit 1
  fi

  log "Booting iOS Simulator ($target_udid)..."
  xcrun simctl boot "$target_udid" 2>/dev/null || true
  # Open Simulator.app to show the window
  open -a Simulator 2>/dev/null || true
  sleep 3
  log "iOS Simulator booted."
}

run_ios() {
  boot_ios_simulator
  local udid
  udid=$(get_booted_ios_udid)

  log "Building iOS app..."
  cd "$MOBILE_DIR"
  # --no-bundler: Metro is already running (started in Step 3).
  # expo run:ios's own app launch fails on macOS due to osascript permission
  # errors, so we handle launch explicitly below.
  npx expo run:ios --no-bundler --device "$udid" 2>&1 | tail -5 || true

  # Terminate any instance that expo may have partially launched.
  xcrun simctl terminate "$udid" com.coyo.app 2>/dev/null || true

  # Mark expo-dev-client onboarding as finished BEFORE launching.
  # Without this, the dev menu auto-shows on every fresh install because
  # isOnboardingFinished defaults to false (see DevMenuManager.swift:86).
  #
  # IMPORTANT: Must write to the app's SANDBOXED plist, not the simulator's
  # global preferences. `xcrun simctl spawn defaults write` writes to the
  # wrong location (/data/Library/Preferences/) — the app reads from its
  # sandbox (/data/Containers/Data/Application/<UUID>/Library/Preferences/).
  local app_container
  app_container=$(xcrun simctl get_app_container "$udid" com.coyo.app data 2>/dev/null || true)
  if [[ -n "$app_container" ]]; then
    local plist="$app_container/Library/Preferences/com.coyo.app.plist"
    /usr/libexec/PlistBuddy -c "Add :EXDevMenuIsOnboardingFinished bool true" "$plist" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Set :EXDevMenuIsOnboardingFinished true" "$plist" 2>/dev/null || true
  fi

  # Launch via deep link so the app connects to Metro immediately.
  sleep 1
  xcrun simctl openurl "$udid" \
    "com.coyo.app://expo-development-client/?url=http%3A%2F%2Flocalhost%3A8081" \
    2>/dev/null || true

  log "iOS app installed and running."
  return 0
}

# ===========================================================================
# Android Emulator
# ===========================================================================

get_android_emulator_id() {
  adb devices 2>/dev/null | grep -E "emulator-[0-9]+\s+device" | awk '{print $1}' | head -1 || true
}

boot_android_emulator() {
  local device_id
  device_id=$(get_android_emulator_id)
  if [[ -n "$device_id" ]]; then
    log "Android Emulator already running: $device_id"
    return
  fi

  if ! command -v adb &>/dev/null; then
    err "adb not found. Install Android SDK platform-tools."
    exit 1
  fi

  # Find the first available AVD
  local avd_name
  avd_name=$("$ANDROID_HOME/emulator/emulator" -list-avds 2>/dev/null | head -1)
  if [[ -z "$avd_name" ]]; then
    err "No Android AVD found. Create one in Android Studio > Virtual Device Manager."
    exit 1
  fi

  log "Starting Android Emulator ($avd_name)..."
  "$ANDROID_HOME/emulator/emulator" -avd "$avd_name" -no-snapshot-load &>/dev/null &
  _PIDS_TO_KILL+=("$!")

  # Wait for emulator to boot
  log "Waiting for emulator to boot..."
  local retries=60
  while true; do
    device_id=$(get_android_emulator_id)
    if [[ -n "$device_id" ]]; then
      # Check if boot completed
      local boot_status
      boot_status=$(adb -s "$device_id" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || true)
      if [[ "$boot_status" == "1" ]]; then
        break
      fi
    fi
    retries=$((retries - 1))
    if [[ $retries -le 0 ]]; then
      err "Android Emulator did not boot within 120 seconds."
      exit 1
    fi
    sleep 2
  done
  log "Android Emulator booted: $device_id"
}

setup_adb_reverse() {
  local device_id="$1"
  adb -s "$device_id" reverse tcp:8081 tcp:8081 2>/dev/null || true
  adb -s "$device_id" reverse tcp:${API_PORT} tcp:${API_PORT} 2>/dev/null || true
  log "adb reverse set up (ports 8081, ${API_PORT})."
}

run_android() {
  boot_android_emulator
  local device_id
  device_id=$(get_android_emulator_id)

  setup_adb_reverse "$device_id"

  log "Building Android app..."
  cd "$MOBILE_DIR"
  # Metro is already running (started in Step 3), so expo detects it on :8081
  # and reuses it instead of spawning its own — no child processes hold the pipe.
  npx expo run:android 2>&1 | tail -5 || true

  # Re-establish adb reverse (build can clear it)
  setup_adb_reverse "$device_id"

  log "Android app installed and running."
  return 0
}

# ===========================================================================
# Main
# ===========================================================================

usage() {
  echo "Usage: $0 {ios|android|both}"
  echo ""
  echo "  ios      Boot iOS Simulator, build, install, and start Metro"
  echo "  android  Start Android Emulator, build, install, and start Metro"
  echo "  both     Start both platforms"
  exit 1
}

if [[ $# -lt 1 ]]; then
  usage
fi

TARGET="$1"

echo ""
info "====================================="
info "  Coyo Development Environment"
info "====================================="
echo ""

# Step 1: Kill leftover Metro to avoid port conflicts during build
kill_existing_metro

# Step 2: Backend infrastructure
ensure_backend

# Step 3: Start Metro in background BEFORE builds
# Apps launched by expo run:* connect to Metro immediately on start.
# Metro must be running first, otherwise the dev client shows an error screen.
log "Starting Metro bundler..."
cd "$MOBILE_DIR"
npx expo start --dev-client &
_METRO_PID=$!
_PIDS_TO_KILL+=("$_METRO_PID")

# Wait for Metro to be ready
log "Waiting for Metro to be ready..."
local_retries=30
while ! curl -sf --max-time 2 http://localhost:8081/status > /dev/null 2>&1; do
  local_retries=$((local_retries - 1))
  if [[ $local_retries -le 0 ]]; then
    err "Metro did not start within 60 seconds."
    exit 1
  fi
  sleep 2
done
log "Metro bundler is ready."

# Step 4: Platform-specific build
case "$TARGET" in
  ios)
    run_ios
    ;;
  android)
    run_android
    ;;
  both)
    run_ios
    run_android
    ;;
  *)
    usage
    ;;
esac

echo ""
log "============================================"
log "  Ready! App is running on $TARGET."
log "============================================"
log ""
log "  Metro bundler running (PID: $_METRO_PID)"
log "  Press Ctrl+C to stop all services."
log ""

# Step 5: Wait on Metro (foreground)
# NOTE: Do NOT use `exec` here — it replaces the shell process and prevents
# the trap handler from firing, leaving backend API and emulator processes
# running after Ctrl+C. Instead, wait on Metro so that when it exits
# (or user presses Ctrl+C), the EXIT trap fires and cleans up.
wait "$_METRO_PID" 2>/dev/null || true
