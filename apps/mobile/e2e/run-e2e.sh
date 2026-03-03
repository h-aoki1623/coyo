#!/usr/bin/env bash
# run-e2e.sh — Build, install, and run Maestro E2E tests on iOS/Android
#
# Usage:
#   ./e2e/run-e2e.sh ios                        # Run all flows on iOS Simulator
#   ./e2e/run-e2e.sh android                    # Run all flows on Android Emulator
#   ./e2e/run-e2e.sh all                        # Run all flows on both (iOS, then Android)
#   ./e2e/run-e2e.sh ios app-launch.yaml        # Run a single flow on iOS
#   ./e2e/run-e2e.sh android navigate-to-history.yaml  # Run a single flow on Android
#   ./e2e/run-e2e.sh ios --skip-build           # Skip native build (app already installed)
#
# Prerequisites:
#   - Maestro CLI installed (maestro --version)
#   - For iOS: a booted iOS Simulator (xcrun simctl list devices booted)
#   - For Android: a running Android Emulator (adb devices)
#
# The script automatically:
#   1. Detects git worktree and symlinks node_modules/.venv from main repo
#   2. Validates prerequisites (Maestro, devices, Docker, Python venv)
#   3. Starts Docker (Postgres + Redis) and backend API if not running
#   4. Kills stale Maestro driver processes to avoid port conflicts
#   5. Builds and installs the app via `npx expo run:*` (unless --skip-build)
#   6. Ensures Maestro driver APKs are installed (Android)
#   7. Sets up adb reverse port forwarding (Android)
#   8. Runs all Maestro flows in the e2e/ directory
#   9. Reports results

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MOBILE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$MOBILE_DIR/../.." && pwd)"
# Main repo root (overridden if in a worktree)
_MAIN_REPO_ROOT="$REPO_ROOT"
# Docker Compose project name (consistent across main repo and worktrees)
_COMPOSE_PROJECT="$(basename "$REPO_ROOT")"
API_DIR="$REPO_ROOT/apps/api"
E2E_DIR="$SCRIPT_DIR"
SCREENSHOTS_DIR="$E2E_DIR/screenshots"

API_PORT=8000
API_HEALTH_URL="http://localhost:${API_PORT}/health"
MAESTRO_PORT=7001
MAESTRO_TIMEOUT=300  # 5 minutes (seconds) per maestro test invocation

# Enable E2E mode: bypasses microphone recording with test audio file
export E2E_MODE=true

# Track whether we started the backend/Metro (for cleanup)
_API_STARTED_BY_SCRIPT=false
_METRO_PID=""
_SKIP_BUILD=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

log()  { echo -e "${GREEN}[e2e]${NC} $*"; }
warn() { echo -e "${YELLOW}[e2e]${NC} $*"; }
err()  { echo -e "${RED}[e2e]${NC} $*" >&2; }

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

# ===========================================================================
# Prerequisites
# ===========================================================================

check_prerequisites() {
  local target="$1"
  local errors=0

  # Maestro CLI
  if ! command -v maestro &>/dev/null; then
    err "Maestro CLI not found. Install with: curl -Ls \"https://get.maestro.mobile.dev\" | bash"
    errors=$((errors + 1))
  fi

  # Docker daemon
  if ! docker info &>/dev/null; then
    log "Docker daemon not running. Attempting to start Docker Desktop..."
    open -a Docker 2>/dev/null || true
    local retries=30
    while ! docker info &>/dev/null; do
      retries=$((retries - 1))
      if [[ $retries -le 0 ]]; then
        err "Docker daemon did not start within 60 seconds."
        errors=$((errors + 1))
        break
      fi
      sleep 2
    done
    if docker info &>/dev/null; then
      log "Docker Desktop started."
    fi
  fi

  # Python venv
  if [[ ! -x "$API_DIR/.venv/bin/python" ]]; then
    err "Python venv not found at $API_DIR/.venv"
    err "Create it with: cd $API_DIR && python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'"
    errors=$((errors + 1))
  else
    # Verify venv is not broken (shebang references correct path)
    local venv_python
    venv_python=$("$API_DIR/.venv/bin/python" -c "import sys; print(sys.executable)" 2>/dev/null || true)
    if [[ -z "$venv_python" ]]; then
      err "Python venv is broken (possibly due to directory rename)."
      err "Recreate it with: cd $API_DIR && python3 -m venv .venv --clear && .venv/bin/pip install -e '.[dev]'"
      errors=$((errors + 1))
    fi
  fi

  # iOS-specific
  if [[ "$target" == "ios" || "$target" == "all" ]]; then
    local udid
    udid=$(get_ios_simulator_udid)
    if [[ -z "$udid" ]]; then
      err "No booted iOS Simulator found. Boot one with: xcrun simctl boot <device>"
      errors=$((errors + 1))
    fi
  fi

  # Android-specific
  if [[ "$target" == "android" || "$target" == "all" ]]; then
    if ! command -v adb &>/dev/null; then
      err "adb not found. Install Android SDK platform-tools."
      errors=$((errors + 1))
    else
      local device_id
      device_id=$(get_android_emulator_id)
      if [[ -z "$device_id" ]]; then
        err "No Android Emulator found. Start one from Android Studio or with: emulator -avd <name>"
        errors=$((errors + 1))
      fi
    fi
  fi

  # expo-dev-client (required for Metro connection on Android/iOS debug builds)
  if ! grep -q '"expo-dev-client"' "$MOBILE_DIR/package.json"; then
    err "expo-dev-client not found in package.json."
    err "Install it with: cd $MOBILE_DIR && npx expo install expo-dev-client"
    errors=$((errors + 1))
  fi

  # Expo dependency compatibility check
  log "Checking Expo dependency compatibility..."
  cd "$MOBILE_DIR"
  local compat_output
  compat_output=$(npx expo install --check 2>&1 || true)
  if echo "$compat_output" | grep -qi "incompatible\|invalid"; then
    warn "Some dependencies may be incompatible with the current Expo SDK:"
    echo "$compat_output" | tail -5
    warn "Run 'npx expo install --fix' to auto-fix."
  fi

  # Test audio fixtures (required for voice conversation E2E)
  local fixtures_dir="$E2E_DIR/fixtures"
  mkdir -p "$fixtures_dir"
  local audio_missing=false
  [[ ! -f "$fixtures_dir/test-audio-clean.m4a" ]] && audio_missing=true
  [[ ! -f "$fixtures_dir/test-audio-errors.m4a" ]] && audio_missing=true

  if $audio_missing; then
    log "Generating missing test audio fixtures..."
    if command -v say &>/dev/null; then
      if [[ ! -f "$fixtures_dir/test-audio-clean.m4a" ]]; then
        say -o "$fixtures_dir/test-audio-clean.m4a" --data-format=aac \
          "Hello, I would like to talk about sports today."
      fi
      if [[ ! -f "$fixtures_dir/test-audio-errors.m4a" ]]; then
        say -o "$fixtures_dir/test-audio-errors.m4a" --data-format=aac \
          "Yesterday I go to the park and I seen many bird. It was very beauty."
      fi
      log "Test audio fixtures generated."
    else
      warn "Test audio not found and 'say' command unavailable (macOS only)."
      warn "Voice conversation E2E flow will fail. Generate them manually:"
      warn "  ./e2e/fixtures/generate-test-audio.sh"
    fi
  fi

  if [[ $errors -gt 0 ]]; then
    err "$errors prerequisite check(s) failed. Fix the above issues and retry."
    exit 1
  fi

  log "All prerequisites satisfied."
}

# ===========================================================================
# Backend
# ===========================================================================

ensure_docker() {
  log "Checking Docker services (Postgres + Redis)..."
  if ! docker compose -f "$REPO_ROOT/docker-compose.yml" -p "$_COMPOSE_PROJECT" ps --status running 2>/dev/null | grep -q "postgres"; then
    log "Starting Docker services..."
    docker compose -f "$REPO_ROOT/docker-compose.yml" -p "$_COMPOSE_PROJECT" up -d
    # Wait for Postgres to be ready
    local retries=10
    while ! docker compose -f "$REPO_ROOT/docker-compose.yml" -p "$_COMPOSE_PROJECT" exec -T postgres pg_isready -U coto -d coto > /dev/null 2>&1; do
      retries=$((retries - 1))
      if [[ $retries -le 0 ]]; then
        err "Postgres did not become ready in time."
        exit 1
      fi
      sleep 2
    done
    log "Docker services are running."
  else
    log "Docker services already running."
  fi
}

ensure_backend() {
  log "Checking backend API at ${API_HEALTH_URL}..."
  if curl -sf --max-time 3 "$API_HEALTH_URL" > /dev/null 2>&1; then
    log "Backend API already running."
    return
  fi

  # Docker must be running before the API
  ensure_docker

  # Run migrations
  log "Running database migrations..."
  cd "$API_DIR"
  .venv/bin/alembic upgrade head 2>&1 | tail -3

  # Start uvicorn in the background
  log "Starting backend API..."
  cd "$API_DIR"
  .venv/bin/uvicorn src.coto.main:app --port "$API_PORT" &
  local api_pid=$!
  _API_STARTED_BY_SCRIPT=true

  # Wait for API to be ready
  local retries=15
  while ! curl -sf --max-time 2 "$API_HEALTH_URL" > /dev/null 2>&1; do
    retries=$((retries - 1))
    if [[ $retries -le 0 ]]; then
      err "Backend API did not start within 30 seconds."
      kill "$api_pid" 2>/dev/null || true
      exit 1
    fi
    sleep 2
  done
  log "Backend API is running (PID: $api_pid)."
}

cleanup() {
  # Stop Metro if we started it
  if [[ -n "$_METRO_PID" ]] && kill -0 "$_METRO_PID" 2>/dev/null; then
    log "Stopping Metro bundler (PID: $_METRO_PID)..."
    kill "$_METRO_PID" 2>/dev/null || true
    sleep 1
    kill -9 "$_METRO_PID" 2>/dev/null || true
  fi

  # Stop backend API if we started it
  if [[ "$_API_STARTED_BY_SCRIPT" == "true" ]]; then
    log "Stopping backend API started by this script..."
    local pids
    pids=$(lsof -ti :"$API_PORT" 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
      echo "$pids" | xargs kill 2>/dev/null || true
    fi
  fi
}

# ===========================================================================
# Maestro
# ===========================================================================

# Portable timeout wrapper (macOS lacks GNU `timeout`).
# Runs a command with a timeout in seconds. Returns 124 on timeout (same as GNU timeout).
run_with_timeout() {
  local timeout_secs="$1"
  shift

  "$@" &
  local cmd_pid=$!

  # Background watchdog that kills the command after timeout
  (
    sleep "$timeout_secs"
    if kill -0 "$cmd_pid" 2>/dev/null; then
      echo -e "${YELLOW}[e2e]${NC} Command timed out after ${timeout_secs}s, killing PID $cmd_pid..."
      kill -9 "$cmd_pid" 2>/dev/null || true
    fi
  ) &
  local watchdog_pid=$!

  # Wait for the command to finish (naturally or killed by watchdog)
  wait "$cmd_pid" 2>/dev/null
  local exit_code=$?

  # Clean up the watchdog if the command finished before timeout
  kill "$watchdog_pid" 2>/dev/null || true
  wait "$watchdog_pid" 2>/dev/null || true

  # Killed by SIGKILL (137) from our watchdog → return 124 (timeout convention)
  if [[ $exit_code -eq 137 ]]; then
    return 124
  fi
  return $exit_code
}

cleanup_maestro() {
  log "Cleaning up stale Maestro processes..."
  local killed=false

  # 1. Kill anything on the Maestro gRPC port
  local pids
  pids=$(lsof -ti :${MAESTRO_PORT} 2>/dev/null || true)
  if [[ -n "$pids" ]]; then
    warn "Killing processes on port ${MAESTRO_PORT}: $pids"
    echo "$pids" | xargs kill -9 2>/dev/null || true
    killed=true
  fi

  # 2. Kill lingering Maestro JVM processes (may have released port already)
  local maestro_pids
  maestro_pids=$(pgrep -f "maestro.cli.AppKt" 2>/dev/null || true)
  if [[ -n "$maestro_pids" ]]; then
    warn "Killing lingering Maestro JVM processes: $maestro_pids"
    echo "$maestro_pids" | xargs kill -9 2>/dev/null || true
    killed=true
  fi

  # 3. Kill Maestro iOS driver processes (maestro-driver-ios)
  local driver_pids
  driver_pids=$(pgrep -f "maestro-driver-ios" 2>/dev/null || true)
  if [[ -n "$driver_pids" ]]; then
    warn "Killing stale Maestro iOS driver processes: $driver_pids"
    echo "$driver_pids" | xargs kill -9 2>/dev/null || true
    killed=true
  fi

  # 4. Kill xcodebuild / XCTRunner processes spawned by the iOS driver
  local xctest_pids
  xctest_pids=$(pgrep -f "xcodebuild.*maestro|XCTRunner" 2>/dev/null || true)
  if [[ -n "$xctest_pids" ]]; then
    warn "Killing stale XCTest/xcodebuild processes: $xctest_pids"
    echo "$xctest_pids" | xargs kill -9 2>/dev/null || true
    killed=true
  fi

  # Give processes time to fully exit before next Maestro invocation.
  # 5 seconds is needed for the XCTest driver to release the accessibility
  # session; 2 seconds was insufficient and caused kAXErrorInvalidUIElement.
  if [[ "$killed" == "true" ]]; then
    sleep 5
  fi
}

# Ensure Maestro driver APKs are installed on Android emulator.
# After emulator wipe-data, the APKs are gone and Maestro cannot connect.
ensure_maestro_driver_apks() {
  local device_id="$1"

  # Check if Maestro driver is already installed
  if adb -s "$device_id" shell pm list packages 2>/dev/null | grep -q "dev.mobile.maestro"; then
    log "Maestro driver APKs already installed."
    return
  fi

  log "Installing Maestro driver APKs..."

  # Find Maestro's lib directory
  local maestro_bin
  maestro_bin="$(command -v maestro)"
  local maestro_lib
  maestro_lib="$(dirname "$maestro_bin")/../lib"

  if [[ ! -f "$maestro_lib/maestro-client.jar" ]]; then
    err "Cannot find maestro-client.jar at $maestro_lib"
    err "Maestro driver APKs must be installed manually."
    return 1
  fi

  # Extract APKs from maestro-client.jar
  local tmp_dir
  tmp_dir=$(mktemp -d)
  cd "$tmp_dir"
  jar xf "$maestro_lib/maestro-client.jar" maestro-server.apk maestro-app.apk 2>/dev/null

  if [[ ! -f maestro-server.apk ]] || [[ ! -f maestro-app.apk ]]; then
    err "Failed to extract Maestro APKs from maestro-client.jar"
    rm -rf "$tmp_dir"
    return 1
  fi

  adb -s "$device_id" install -r maestro-server.apk 2>&1 | tail -1
  adb -s "$device_id" install -r maestro-app.apk 2>&1 | tail -1

  rm -rf "$tmp_dir"
  log "Maestro driver APKs installed."
}

# Start the Maestro gRPC driver on Android and set up port forwarding.
# This is needed because Maestro sometimes fails to auto-start the driver.
start_maestro_driver() {
  local device_id="$1"

  cleanup_maestro

  log "Starting Maestro instrumentation server..."
  adb -s "$device_id" shell am instrument -w -e debug false \
    dev.mobile.maestro.test/androidx.test.runner.AndroidJUnitRunner > /dev/null 2>&1 &
  sleep 5
  adb -s "$device_id" forward tcp:${MAESTRO_PORT} tcp:${MAESTRO_PORT} 2>/dev/null || true
  log "Maestro driver ready on port ${MAESTRO_PORT}."
}

# ===========================================================================
# Android: adb reverse
# ===========================================================================

# Set up reverse port forwarding so localhost:<port> on the emulator
# reaches localhost:<port> on the host. This is required because the app
# uses http://localhost:8000 as the API base URL.
setup_adb_reverse() {
  local device_id="$1"
  adb -s "$device_id" reverse tcp:8081 tcp:8081 2>/dev/null || true
  adb -s "$device_id" reverse tcp:${API_PORT} tcp:${API_PORT} 2>/dev/null || true
}

# Verify adb reverse is active. Building/installing an APK can clear it.
verify_adb_reverse() {
  local device_id="$1"
  local current
  current=$(adb -s "$device_id" reverse --list 2>/dev/null || true)
  if ! echo "$current" | grep -q "tcp:${API_PORT}"; then
    warn "adb reverse was cleared (likely by APK install). Re-establishing..."
    setup_adb_reverse "$device_id"
  fi
}

# ===========================================================================
# Device detection
# ===========================================================================

get_ios_simulator_udid() {
  local udid
  udid=$(xcrun simctl list devices booted -j 2>/dev/null \
    | python3 -c "
import json, sys
data = json.load(sys.stdin)
for runtime, devices in data.get('devices', {}).items():
    for d in devices:
        if d.get('state') == 'Booted':
            print(d['udid'])
            sys.exit(0)
sys.exit(1)
" 2>/dev/null) || true
  echo "$udid"
}

get_android_emulator_id() {
  adb devices 2>/dev/null | grep -E "emulator-[0-9]+\s+device" | awk '{print $1}' | head -1
}

# ===========================================================================
# iOS
# ===========================================================================

run_ios() {
  log "=== iOS E2E Tests ==="

  cleanup_maestro

  local udid
  udid=$(get_ios_simulator_udid)
  if [[ -z "$udid" ]]; then
    err "No booted iOS Simulator found. Boot one with: xcrun simctl boot <device>"
    exit 1
  fi
  log "Using iOS Simulator: $udid"

  if [[ "$_SKIP_BUILD" != "true" ]]; then
    # Build and install (--no-bundler: build only, don't start Metro)
    log "Building iOS app..."
    cd "$MOBILE_DIR"
    if ! npx expo run:ios --device "$udid" --no-bundler 2>&1 | tail -20; then
      warn "Build command exited with non-zero status. Checking if app was installed..."
    fi

    # Verify installation
    if ! xcrun simctl listapps "$udid" 2>/dev/null | grep -q "com.coto.app"; then
      err "iOS app not installed on simulator. Build may have failed."
      exit 1
    fi
    log "iOS app installed successfully."
  else
    log "Skipping iOS build (--skip-build)."
    if ! xcrun simctl listapps "$udid" 2>/dev/null | grep -q "com.coto.app"; then
      err "iOS app not installed on simulator. Cannot skip build."
      exit 1
    fi
  fi

  # Start Metro bundler in the background (--dev-client matches expo-dev-client URL scheme)
  log "Starting Metro bundler..."
  cd "$MOBILE_DIR"
  npx expo start --dev-client --port 8081 > /tmp/metro-e2e.log 2>&1 &
  local metro_pid=$!
  _METRO_PID="$metro_pid"

  # Phase 1: wait for Metro HTTP server to start (fast)
  local retries=30
  while ! curl -sf --max-time 2 "http://localhost:8081/status" > /dev/null 2>&1; do
    retries=$((retries - 1))
    if [[ $retries -le 0 ]]; then
      err "Metro bundler did not start within 60 seconds."
      kill "$metro_pid" 2>/dev/null || true
      exit 1
    fi
    sleep 2
  done
  log "Metro HTTP server is up. Waiting for iOS bundle compilation..."

  # Phase 2: wait for the JS bundle to finish compiling (slow on first run)
  local bundle_retries=5
  while ! curl -sf --max-time 120 \
      "http://localhost:8081/index.bundle?platform=ios&dev=true&minify=false" \
      -o /dev/null 2>/dev/null; do
    bundle_retries=$((bundle_retries - 1))
    if [[ $bundle_retries -le 0 ]]; then
      err "Metro iOS bundle did not compile within timeout."
      kill "$metro_pid" 2>/dev/null || true
      exit 1
    fi
    warn "Bundle not ready yet, retrying ($bundle_retries attempts left)..."
  done
  log "Metro bundler is ready — iOS bundle compiled (PID: $metro_pid)."

  # Launch the app so it connects to Metro before Maestro takes over
  log "Launching app to connect to Metro..."
  xcrun simctl launch "$udid" com.coto.app 2>/dev/null || true
  sleep 3

  # Dismiss expo-dev-client onboarding dialog if present (first launch only)
  log "Pre-dismissing expo-dev-client onboarding dialog..."
  cleanup_maestro
  maestro --platform ios --udid "$udid" test "$E2E_DIR/helpers/dismiss-dev-client.yaml" 2>/dev/null || true

  # Run Maestro tests (retry once on failure to handle flaky XCTest driver errors).
  # Each invocation is wrapped with `timeout` to prevent indefinite hangs
  # caused by kAXErrorInvalidUIElement (Apple XCTest framework issue).
  log "Running Maestro tests on iOS..."
  mkdir -p "$SCREENSHOTS_DIR"
  cd "$SCREENSHOTS_DIR"
  cleanup_maestro
  local exit_code=0
  run_with_timeout "${MAESTRO_TIMEOUT}" maestro --platform ios --udid "$udid" test "$_FLOW_TARGET" || exit_code=$?

  if [[ $exit_code -ne 0 ]]; then
    if [[ $exit_code -eq 124 ]]; then
      warn "iOS tests timed out after ${MAESTRO_TIMEOUT}s (likely kAXErrorInvalidUIElement). Retrying..."
    else
      warn "iOS tests failed (exit code: $exit_code). Retrying once..."
    fi
    cleanup_maestro

    # Reset the simulator's accessibility session to recover from
    # kAXErrorInvalidUIElement. The shutdown/boot cycle forces the
    # Accessibility framework to reinitialize its element tree.
    log "Resetting iOS Simulator to recover accessibility session..."
    xcrun simctl shutdown "$udid" 2>/dev/null || true
    sleep 2
    xcrun simctl boot "$udid" 2>/dev/null || true
    sleep 3

    # Re-launch the app to reconnect to Metro
    xcrun simctl launch "$udid" com.coto.app 2>/dev/null || true
    sleep 3

    exit_code=0
    run_with_timeout "${MAESTRO_TIMEOUT}" maestro --platform ios --udid "$udid" test "$_FLOW_TARGET" || exit_code=$?
  fi

  # Stop Metro
  kill "$metro_pid" 2>/dev/null || true

  log "iOS E2E tests finished (exit code: $exit_code)"
  return $exit_code
}

# ===========================================================================
# Android
# ===========================================================================

run_android() {
  log "=== Android E2E Tests ==="

  cleanup_maestro

  local device_id
  device_id=$(get_android_emulator_id)
  if [[ -z "$device_id" ]]; then
    err "No Android Emulator found. Start one from Android Studio or with: emulator -avd <name>"
    exit 1
  fi
  log "Using Android Emulator: $device_id"

  # Set up reverse port forwarding for Metro and API
  setup_adb_reverse "$device_id"

  if [[ "$_SKIP_BUILD" != "true" ]]; then
    # Build and install (--no-bundler: build only, don't start Metro)
    log "Building Android app..."
    cd "$MOBILE_DIR"
    npx expo run:android --no-bundler 2>&1 | tail -5

    # Verify installation
    if ! adb -s "$device_id" shell pm list packages 2>/dev/null | grep -q "com.coto.app"; then
      err "Android app not installed on emulator. Build may have failed."
      exit 1
    fi
    log "Android app installed successfully."
  else
    log "Skipping Android build (--skip-build)."
    if ! adb -s "$device_id" shell pm list packages 2>/dev/null | grep -q "com.coto.app"; then
      err "Android app not installed on emulator. Cannot skip build."
      exit 1
    fi
  fi

  # Re-establish reverse port forwarding (build/install can clear adb state)
  verify_adb_reverse "$device_id"

  # Ensure Maestro driver APKs are installed (may be missing after wipe-data)
  ensure_maestro_driver_apks "$device_id"

  # Start Metro bundler in the background (--dev-client matches expo-dev-client URL scheme)
  log "Starting Metro bundler..."
  cd "$MOBILE_DIR"
  npx expo start --dev-client --port 8081 > /tmp/metro-e2e-android.log 2>&1 &
  local metro_pid=$!
  _METRO_PID="$metro_pid"

  # Phase 1: wait for Metro HTTP server to start (fast)
  local retries=30
  while ! curl -sf --max-time 2 "http://localhost:8081/status" > /dev/null 2>&1; do
    retries=$((retries - 1))
    if [[ $retries -le 0 ]]; then
      err "Metro bundler did not start within 60 seconds."
      kill "$metro_pid" 2>/dev/null || true
      exit 1
    fi
    sleep 2
  done
  log "Metro HTTP server is up. Waiting for Android bundle compilation..."

  # Phase 2: wait for the JS bundle to finish compiling (slow on first run)
  local bundle_retries=5
  while ! curl -sf --max-time 120 \
      "http://localhost:8081/index.bundle?platform=android&dev=true&minify=false" \
      -o /dev/null 2>/dev/null; do
    bundle_retries=$((bundle_retries - 1))
    if [[ $bundle_retries -le 0 ]]; then
      err "Metro Android bundle did not compile within timeout."
      kill "$metro_pid" 2>/dev/null || true
      exit 1
    fi
    warn "Bundle not ready yet, retrying ($bundle_retries attempts left)..."
  done
  log "Metro bundler is ready — Android bundle compiled (PID: $metro_pid)."

  # Re-verify adb reverse after Metro start
  verify_adb_reverse "$device_id"

  # Launch the app so it connects to Metro before Maestro takes over
  log "Launching app to connect to Metro..."
  adb -s "$device_id" shell am start -a android.intent.action.VIEW \
    -d "exp+coto://expo-development-client/?url=http%3A%2F%2Flocalhost%3A8081" \
    com.coto.app 2>/dev/null || true
  sleep 3

  # Dismiss expo-dev-client onboarding dialog if present (first launch only)
  log "Pre-dismissing expo-dev-client onboarding dialog..."
  start_maestro_driver "$device_id"
  verify_adb_reverse "$device_id"
  maestro --platform android --udid "$device_id" test "$E2E_DIR/helpers/dismiss-dev-client.yaml" 2>/dev/null || true

  # Run Maestro tests (retry once on failure to handle flaky driver errors).
  # Each invocation is wrapped with `timeout` to prevent indefinite hangs.
  log "Running Maestro tests on Android..."
  mkdir -p "$SCREENSHOTS_DIR"
  cd "$SCREENSHOTS_DIR"
  cleanup_maestro
  start_maestro_driver "$device_id"
  verify_adb_reverse "$device_id"
  local exit_code=0
  run_with_timeout "${MAESTRO_TIMEOUT}" maestro --platform android --udid "$device_id" test "$_FLOW_TARGET" || exit_code=$?

  if [[ $exit_code -ne 0 ]]; then
    warn "Android tests failed (exit code: $exit_code). Retrying once..."
    cleanup_maestro
    start_maestro_driver "$device_id"
    verify_adb_reverse "$device_id"
    exit_code=0
    run_with_timeout "${MAESTRO_TIMEOUT}" maestro --platform android --udid "$device_id" test "$_FLOW_TARGET" || exit_code=$?
  fi

  # Stop Metro
  kill "$metro_pid" 2>/dev/null || true

  log "Android E2E tests finished (exit code: $exit_code)"
  return $exit_code
}

# ===========================================================================
# Main
# ===========================================================================

usage() {
  echo "Usage: $0 {ios|android|all} [--skip-build] [flow.yaml]"
  echo ""
  echo "  ios      Run E2E tests on iOS Simulator"
  echo "  android  Run E2E tests on Android Emulator"
  echo "  all      Run on both (iOS first, then Android)"
  echo ""
  echo "Options:"
  echo "  --skip-build  Skip native build+install (use already-installed app)"
  echo ""
  echo "  Optional: specify a single flow file (e.g., app-launch.yaml)"
  echo "            to run only that flow instead of the full suite."
  exit 1
}

# Ensure cleanup on exit, Ctrl+C, or kill
trap cleanup EXIT INT TERM

if [[ $# -lt 1 ]]; then
  usage
fi

# Parse target (first positional arg)
_TARGET="$1"
shift

case "$_TARGET" in
  ios|android|all) ;;
  *) usage ;;
esac

# Parse remaining args: [--skip-build] [flow.yaml]
_FLOW_TARGET=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-build)
      _SKIP_BUILD=true
      shift
      ;;
    -*)
      err "Unknown option: $1"
      usage
      ;;
    *)
      if [[ -n "$_FLOW_TARGET" ]]; then
        err "Only one flow file can be specified."
        usage
      fi
      if [[ ! -f "$E2E_DIR/$1" ]]; then
        err "Flow file not found: $E2E_DIR/$1"
        exit 1
      fi
      _FLOW_TARGET="$E2E_DIR/$1"
      log "Single flow mode: $1"
      shift
      ;;
  esac
done

if [[ -z "$_FLOW_TARGET" ]]; then
  _FLOW_TARGET="$E2E_DIR/"
fi

# Symlink dependencies if running inside a git worktree
ensure_worktree_deps

# Validate all prerequisites upfront before doing any work
check_prerequisites "$_TARGET"

# Kill any existing Metro process on port 8081 to avoid "Use port 8082?" prompt
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
kill_existing_metro

# Sweep any rogue Maestro processes started outside this script
# (e.g., 'maestro hierarchy' run manually in another terminal)
cleanup_maestro

# Always ensure backend is running before E2E tests
ensure_backend

case "$_TARGET" in
  ios)
    run_ios
    ;;
  android)
    run_android
    ;;
  all)
    ios_result=0
    android_result=0

    run_ios || ios_result=$?
    run_android || android_result=$?

    echo ""
    log "=== Summary ==="
    if [[ $ios_result -eq 0 ]]; then
      log "iOS:     ${GREEN}PASSED${NC}"
    else
      err "iOS:     ${RED}FAILED${NC} (exit code: $ios_result)"
    fi
    if [[ $android_result -eq 0 ]]; then
      log "Android: ${GREEN}PASSED${NC}"
    else
      err "Android: ${RED}FAILED${NC} (exit code: $android_result)"
    fi

    [[ $ios_result -eq 0 && $android_result -eq 0 ]]
    ;;
  *)
    usage
    ;;
esac
