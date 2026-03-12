#!/usr/bin/env bash
# run-e2e.sh — Run Maestro E2E tests on iOS/Android
#
# Usage:
#   ./e2e/run-e2e.sh ios                               # Run all flows on iOS Simulator
#   ./e2e/run-e2e.sh android                            # Run all flows on Android Emulator
#   ./e2e/run-e2e.sh all                                # Run all flows on both (iOS, then Android)
#   ./e2e/run-e2e.sh ios app-launch.yaml                # Run a single flow on iOS
#   ./e2e/run-e2e.sh android navigate-to-history.yaml   # Run a single flow on Android
#
# Prerequisites:
#   - Dev environment running (make dev-ios / make dev-android / make dev-both)
#   - Maestro CLI installed (maestro --version)
#
# The dev environment (run-dev.sh) handles:
#   - Docker (Postgres + Redis)
#   - Backend API
#   - Metro bundler
#   - iOS Simulator / Android Emulator boot
#   - App build and install
#
# This script only:
#   1. Validates the dev environment is running (API, Metro, device, app)
#   2. Sweeps rogue Maestro processes to avoid port conflicts
#   3. Ensures Maestro driver APKs are installed (Android)
#   4. Runs Maestro test flows with retry on failure
#   5. Reports results

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MOBILE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$MOBILE_DIR/../.." && pwd)"
API_DIR="$REPO_ROOT/apps/api"
E2E_DIR="$SCRIPT_DIR"
SCREENSHOTS_DIR="$E2E_DIR/screenshots"

# Load shared functions
source "$REPO_ROOT/scripts/lib/common.sh"
init_log "[e2e]"
init_worktree

MAESTRO_PORT=7001
MAESTRO_TIMEOUT=300  # 5 minutes (seconds) per maestro test invocation

# Enable E2E mode: bypasses microphone recording with test audio file
export E2E_MODE=true

# ===========================================================================
# Environment validation
# ===========================================================================

require_environment() {
  local target="$1"
  local errors=0

  # Maestro CLI
  if ! command -v maestro &>/dev/null; then
    err "Maestro CLI not found. Install with: curl -Ls \"https://get.maestro.mobile.dev\" | bash"
    errors=$((errors + 1))
  fi

  # Backend API
  if ! curl -sf --max-time 3 "$API_HEALTH_URL" > /dev/null 2>&1; then
    err "Backend API is not running at $API_HEALTH_URL"
    err "Start the dev environment first: make dev-ios / make dev-android"
    errors=$((errors + 1))
  fi

  # Metro bundler
  if ! curl -sf --max-time 2 "http://localhost:8081/status" > /dev/null 2>&1; then
    err "Metro bundler is not running on port 8081"
    err "Start the dev environment first: make dev-ios / make dev-android"
    errors=$((errors + 1))
  fi

  # iOS-specific
  if [[ "$target" == "ios" || "$target" == "all" ]]; then
    local udid
    udid=$(get_booted_ios_udid)
    if [[ -z "$udid" ]]; then
      err "No booted iOS Simulator found."
      err "Start the dev environment first: make dev-ios"
      errors=$((errors + 1))
    else
      # Verify app is installed
      if ! xcrun simctl listapps "$udid" 2>/dev/null | grep -q "to.coyo.app"; then
        err "iOS app (to.coyo.app) not installed on simulator."
        err "Start the dev environment first: make dev-ios"
        errors=$((errors + 1))
      fi
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
        err "No Android Emulator found."
        err "Start the dev environment first: make dev-android"
        errors=$((errors + 1))
      else
        # Verify app is installed
        if ! adb -s "$device_id" shell pm list packages 2>/dev/null | grep -q "to.coyo.app"; then
          err "Android app (to.coyo.app) not installed on emulator."
          err "Start the dev environment first: make dev-android"
          errors=$((errors + 1))
        fi
      fi
    fi
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
    err "$errors prerequisite check(s) failed."
    err "Start the dev environment first: make dev-ios / make dev-android / make dev-both"
    exit 1
  fi

  log "Environment ready."
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
      warn "Command timed out after ${timeout_secs}s, killing PID $cmd_pid..."
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

  # Killed by SIGKILL (137) from our watchdog -> return 124 (timeout convention)
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

  # Extract APKs from maestro-client.jar (run in subshell to avoid cd side effects)
  local tmp_dir
  tmp_dir=$(mktemp -d)
  (
    cd "$tmp_dir"
    jar xf "$maestro_lib/maestro-client.jar" maestro-server.apk maestro-app.apk 2>/dev/null
  )

  if [[ ! -f "$tmp_dir/maestro-server.apk" ]] || [[ ! -f "$tmp_dir/maestro-app.apk" ]]; then
    err "Failed to extract Maestro APKs from maestro-client.jar"
    rm -rf "$tmp_dir"
    return 1
  fi

  adb -s "$device_id" install -r "$tmp_dir/maestro-server.apk" 2>&1 | tail -1
  adb -s "$device_id" install -r "$tmp_dir/maestro-app.apk" 2>&1 | tail -1

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

# Verify adb reverse is active. Maestro operations can clear it.
verify_adb_reverse() {
  local device_id="$1"
  local current
  current=$(adb -s "$device_id" reverse --list 2>/dev/null || true)
  if ! echo "$current" | grep -q "tcp:${API_PORT}"; then
    warn "adb reverse was cleared. Re-establishing..."
    setup_adb_reverse "$device_id"
  fi
}

# ===========================================================================
# iOS
# ===========================================================================

run_ios() {
  log "=== iOS E2E Tests ==="

  cleanup_maestro

  local udid
  udid=$(get_booted_ios_udid)
  log "Using iOS Simulator: $udid"

  # Verify Metro is serving iOS bundles
  log "Verifying Metro bundle availability for iOS..."
  if ! curl -sf --max-time 120 \
      "http://localhost:8081/index.bundle?platform=ios&dev=true&minify=false" \
      -o /dev/null 2>/dev/null; then
    err "Metro is not serving iOS bundles. Check Metro bundler output."
    exit 1
  fi
  log "Metro iOS bundle is ready."

  # Launch the app so it connects to Metro before Maestro takes over
  log "Launching app to connect to Metro..."
  xcrun simctl launch "$udid" to.coyo.app 2>/dev/null || true
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
    xcrun simctl launch "$udid" to.coyo.app 2>/dev/null || true
    sleep 3

    exit_code=0
    run_with_timeout "${MAESTRO_TIMEOUT}" maestro --platform ios --udid "$udid" test "$_FLOW_TARGET" || exit_code=$?
  fi

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
  log "Using Android Emulator: $device_id"

  # Ensure adb reverse is set up
  setup_adb_reverse "$device_id"

  # Ensure Maestro driver APKs are installed (may be missing after wipe-data)
  ensure_maestro_driver_apks "$device_id"

  # Verify Metro is serving Android bundles
  log "Verifying Metro bundle availability for Android..."
  if ! curl -sf --max-time 120 \
      "http://localhost:8081/index.bundle?platform=android&dev=true&minify=false" \
      -o /dev/null 2>/dev/null; then
    err "Metro is not serving Android bundles. Check Metro bundler output."
    exit 1
  fi
  log "Metro Android bundle is ready."

  # Re-verify adb reverse
  verify_adb_reverse "$device_id"

  # Launch the app so it connects to Metro before Maestro takes over
  log "Launching app to connect to Metro..."
  adb -s "$device_id" shell am start -a android.intent.action.VIEW \
    -d "exp+coyo://expo-development-client/?url=http%3A%2F%2Flocalhost%3A8081" \
    to.coyo.app 2>/dev/null || true
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

  log "Android E2E tests finished (exit code: $exit_code)"
  return $exit_code
}

# ===========================================================================
# Main
# ===========================================================================

usage() {
  echo "Usage: $0 {ios|android|all} [flow.yaml]"
  echo ""
  echo "  ios      Run E2E tests on iOS Simulator"
  echo "  android  Run E2E tests on Android Emulator"
  echo "  all      Run on both (iOS first, then Android)"
  echo ""
  echo "  Optional: specify a single flow file (e.g., app-launch.yaml)"
  echo "            to run only that flow instead of the full suite."
  echo ""
  echo "  Requires: dev environment running (make dev-ios / make dev-android)"
  exit 1
}

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

# Parse remaining args: [flow.yaml]
_FLOW_TARGET=""
while [[ $# -gt 0 ]]; do
  case "$1" in
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

# Validate dev environment is running
require_environment "$_TARGET"

# Sweep any rogue Maestro processes started outside this script
cleanup_maestro

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
      log "iOS:     PASSED"
    else
      err "iOS:     FAILED (exit code: $ios_result)"
    fi
    if [[ $android_result -eq 0 ]]; then
      log "Android: PASSED"
    else
      err "Android: FAILED (exit code: $android_result)"
    fi

    [[ $ios_result -eq 0 && $android_result -eq 0 ]]
    ;;
  *)
    usage
    ;;
esac
