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
#   - Maestro CLI installed (maestro --version)
#
# Dev environment (run-dev.sh) is started automatically if not already running.
# run-dev.sh handles: Docker, Backend API, Metro, Simulator/Emulator, app build.
#
# This script:
#   1. Ensures dev environment is running (delegates to run-dev.sh --background)
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
RESULTS_DIR="$E2E_DIR/results"

# Load shared functions
source "$REPO_ROOT/scripts/lib/common.sh"
init_log "[e2e]"
init_worktree

MAESTRO_PORT=7001
MAESTRO_TIMEOUT=600  # 10 minutes (seconds) per maestro test invocation.
# This is a hang guard (e.g. kAXErrorInvalidUIElement), not a performance
# assertion — per-step timeouts inside the flows still enforce responsiveness.
# 420s proved too tight on a loaded Android emulator: the full 8-flow suite
# needs ~480-500s there (voice-conversation alone takes ~4min with real
# audio playback), so a healthy run was killed before the last two flows.

# Enable E2E mode: bypasses microphone recording with test audio file
export E2E_MODE=true

# ===========================================================================
# Result file output (defense against lost stdout in background execution)
# ===========================================================================

# Write a machine-readable result file so that the outcome can be checked
# even when stdout/stderr capture fails (e.g. Claude Code background tasks).
# Result files are written to apps/mobile/e2e/results/.
write_result() {
  local _wr_platform="$1"   # ios | android | all
  local _wr_status="$2"     # PASS | FAIL
  local _wr_duration="$3"   # seconds
  local _wr_details="${4:-}" # optional: failure details

  mkdir -p "$RESULTS_DIR"

  local _wr_ts
  _wr_ts=$(date +%Y%m%d-%H%M%S)
  local _wr_file="$RESULTS_DIR/e2e-result-${_wr_platform}-${_wr_ts}.txt"

  {
    echo "platform: $_wr_platform"
    echo "status: $_wr_status"
    echo "duration: ${_wr_duration}s"
    echo "timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    if [[ -n "$_wr_details" ]]; then
      echo "details: $_wr_details"
    fi
  } > "$_wr_file"

  # Update the latest symlink for quick access
  ln -sf "$(basename "$_wr_file")" "$RESULTS_DIR/e2e-result-latest.txt"

  log "Result written to: $_wr_file"
}

# ===========================================================================
# Environment setup
# ===========================================================================

ensure_dev_environment() {
  local target="$1"

  # Maestro CLI (E2E-specific prerequisite, not a dev environment concern)
  if ! command -v maestro &>/dev/null; then
    err "Maestro CLI not found. Install with: curl -Ls \"https://get.maestro.mobile.dev\" | bash"
    exit 1
  fi

  # Map e2e target to run-dev.sh target (e2e "all" = dev "both")
  local dev_target="$target"
  if [[ "$target" == "all" ]]; then
    dev_target="both"
  fi

  # Delegate dev environment setup to run-dev.sh (idempotent — skips
  # components that are already running).
  log "Ensuring dev environment is running (target: $dev_target)..."
  if ! "$MOBILE_DIR/run-dev.sh" "$dev_target" --background; then
    err "Failed to start dev environment. See errors above."
    exit 1
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
  local _start_time=$SECONDS

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

    # Verify Metro is still serving bundles after Simulator reset.
    # Without this check, the app may launch to a black screen because it
    # cannot fetch the JS bundle from Metro.
    log "Verifying Metro bundle availability before retry..."
    if ! curl -sf --max-time 30 \
        "http://localhost:8081/index.bundle?platform=ios&dev=true&minify=false" \
        -o /dev/null 2>/dev/null; then
      err "Metro is not serving iOS bundles after Simulator reset. Aborting retry."
      return 1
    fi
    log "Metro iOS bundle is ready."

    # Re-launch the app to reconnect to Metro
    xcrun simctl launch "$udid" to.coyo.app 2>/dev/null || true
    sleep 5

    # Warm-up: wait for the app to fully render before Maestro takes over.
    # The extra delay prevents the black-screen crash observed when Maestro
    # starts interacting before the JS bundle has finished loading.
    log "Waiting for app to stabilize after relaunch..."
    sleep 3

    exit_code=0
    run_with_timeout "${MAESTRO_TIMEOUT}" maestro --platform ios --udid "$udid" test "$_FLOW_TARGET" || exit_code=$?
  fi

  local _duration=$(( SECONDS - _start_time ))
  if [[ $exit_code -eq 0 ]]; then
    write_result "ios" "PASS" "$_duration"
  else
    write_result "ios" "FAIL" "$_duration" "exit code: $exit_code"
  fi

  log "iOS E2E tests finished (exit code: $exit_code)"
  return $exit_code
}

# ===========================================================================
# Android
# ===========================================================================

run_android() {
  log "=== Android E2E Tests ==="
  local _start_time=$SECONDS

  cleanup_maestro

  local device_id
  device_id=$(get_android_emulator_id)
  log "Using Android Emulator: $device_id"

  # Disable Android autofill to prevent Google Password Manager dialogs
  # from blocking input fields during E2E tests
  log "Disabling Android autofill service..."
  adb -s "$device_id" shell settings put secure autofill_service null 2>/dev/null || true

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

  local _duration=$(( SECONDS - _start_time ))
  if [[ $exit_code -eq 0 ]]; then
    write_result "android" "PASS" "$_duration"
  else
    write_result "android" "FAIL" "$_duration" "exit code: $exit_code"
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
  echo "  Dev environment is started automatically if not already running."
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

# Ensure dev environment is running (starts if needed)
ensure_dev_environment "$_TARGET"

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
    _all_start=$SECONDS
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

    # Write combined result file for "all" target
    _all_duration=$(( SECONDS - _all_start ))
    if [[ $ios_result -eq 0 && $android_result -eq 0 ]]; then
      write_result "all" "PASS" "$_all_duration"
    else
      _fail_details=""
      [[ $ios_result -ne 0 ]] && _fail_details="ios(exit:$ios_result)"
      [[ $android_result -ne 0 ]] && _fail_details="${_fail_details:+$_fail_details, }android(exit:$android_result)"
      write_result "all" "FAIL" "$_all_duration" "$_fail_details"
    fi

    [[ $ios_result -eq 0 && $android_result -eq 0 ]]
    ;;
  *)
    usage
    ;;
esac
