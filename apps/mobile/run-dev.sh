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
API_DIR="$REPO_ROOT/apps/api"

# Load shared functions
source "$REPO_ROOT/scripts/lib/common.sh"
init_log "[dev]"
init_worktree

# Track PIDs for cleanup
_PIDS_TO_KILL=()

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
  if [[ -n "$_BACKEND_PID" ]]; then
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
# iOS: Build and install
# ===========================================================================

run_ios() {
  boot_ios_simulator
  local udid
  udid=$(get_booted_ios_udid)

  log "Building iOS app..."
  cd "$MOBILE_DIR"

  # Prebuild native project if needed
  if [[ ! -d "ios" ]]; then
    log "Running expo prebuild..."
    npx expo prebuild --platform ios --clean 2>&1 | tail -5
  fi

  # Xcode 17 workaround: pre-generate FirebaseAuth-Swift.h
  if [[ ! -f "ios/Pods/Headers/Public/FirebaseAuth/FirebaseAuth-Swift.h" ]]; then
    if [[ -f "scripts/fix-firebase-swift-header.sh" ]]; then
      log "Generating FirebaseAuth-Swift.h (Xcode 17 workaround)..."
      bash scripts/fix-firebase-swift-header.sh
    fi
  fi

  # Build with xcodebuild (expo run:ios fails on Xcode 17 beta due to
  # devicectl JSON format changes that misidentify simulator as physical device)
  log "Building with xcodebuild..."
  xcodebuild \
    -workspace ios/Coyo.xcworkspace \
    -scheme Coyo \
    -destination "platform=iOS Simulator,id=$udid" \
    -configuration Debug \
    build \
    -quiet 2>&1 | tail -5 || true

  # Find and install the built app
  local app_path
  app_path=$(find ~/Library/Developer/Xcode/DerivedData -name "Coyo.app" \
    -path "*Debug-iphonesimulator*" -newer ios/Podfile 2>/dev/null | head -1)
  if [[ -n "$app_path" ]]; then
    xcrun simctl install "$udid" "$app_path"
  fi

  # Terminate any instance that expo may have partially launched.
  xcrun simctl terminate "$udid" to.coyo.app 2>/dev/null || true

  # Mark expo-dev-client onboarding as finished BEFORE launching.
  # Without this, the dev menu auto-shows on every fresh install because
  # isOnboardingFinished defaults to false (see DevMenuManager.swift:86).
  #
  # IMPORTANT: Must write to the app's SANDBOXED plist, not the simulator's
  # global preferences. `xcrun simctl spawn defaults write` writes to the
  # wrong location (/data/Library/Preferences/) — the app reads from its
  # sandbox (/data/Containers/Data/Application/<UUID>/Library/Preferences/).
  local app_container
  app_container=$(xcrun simctl get_app_container "$udid" to.coyo.app data 2>/dev/null || true)
  if [[ -n "$app_container" ]]; then
    local plist="$app_container/Library/Preferences/to.coyo.app.plist"
    /usr/libexec/PlistBuddy -c "Add :EXDevMenuIsOnboardingFinished bool true" "$plist" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Set :EXDevMenuIsOnboardingFinished true" "$plist" 2>/dev/null || true
  fi

  # Launch via deep link so the app connects to Metro immediately.
  sleep 1
  xcrun simctl openurl "$udid" \
    "to.coyo.app://expo-development-client/?url=http%3A%2F%2Flocalhost%3A8081" \
    2>/dev/null || true

  log "iOS app installed and running."
  return 0
}

# ===========================================================================
# Android: Build and install
# ===========================================================================

run_android() {
  boot_android_emulator
  if [[ -n "$_EMULATOR_PID" ]]; then
    _PIDS_TO_KILL+=("$_EMULATOR_PID")
  fi

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

# Step 1: Validate Firebase config files before prebuild
FIREBASE_DIR="$MOBILE_DIR/firebase/development"
IOS_PLIST="$FIREBASE_DIR/GoogleService-Info.plist"
ANDROID_JSON="$FIREBASE_DIR/google-services.json"

if [[ ! -f "$IOS_PLIST" ]] || [[ ! -f "$ANDROID_JSON" ]]; then
  # Auto-copy fallback: if config files exist at the mobile root (legacy location),
  # copy them into firebase/development/ so app.config.ts can find them.
  LEGACY_PLIST="$MOBILE_DIR/GoogleService-Info.plist"
  LEGACY_JSON="$MOBILE_DIR/google-services.json"

  if [[ -f "$LEGACY_PLIST" ]] || [[ -f "$LEGACY_JSON" ]]; then
    warn "Firebase config not found in firebase/development/."
    warn "Copying from legacy location (apps/mobile/ root)..."
    mkdir -p "$FIREBASE_DIR"
    [[ -f "$LEGACY_PLIST" ]] && cp "$LEGACY_PLIST" "$IOS_PLIST"
    [[ -f "$LEGACY_JSON" ]]  && cp "$LEGACY_JSON"  "$ANDROID_JSON"
    log "Firebase config copied to firebase/development/."

    # Verify both files are now present after the copy
    if [[ ! -f "$IOS_PLIST" ]] || [[ ! -f "$ANDROID_JSON" ]]; then
      err "Firebase config is still incomplete after legacy copy."
      [[ ! -f "$IOS_PLIST" ]]   && err "  Missing: GoogleService-Info.plist (iOS)"
      [[ ! -f "$ANDROID_JSON" ]] && err "  Missing: google-services.json (Android)"
      err ""
      err "Download the missing file(s) from the Firebase Console"
      err "and place them in: apps/mobile/firebase/development/"
      exit 1
    fi
  else
    err "Firebase config files not found."
    err "Expected: $IOS_PLIST"
    err "Expected: $ANDROID_JSON"
    err ""
    err "Download them from the Firebase Console:"
    err "  1. Go to Firebase Console > Project Settings > General"
    err "  2. Download GoogleService-Info.plist (iOS) and google-services.json (Android)"
    err "  3. Place them in: apps/mobile/firebase/development/"
    exit 1
  fi
fi
log "Firebase config validated."

# Step 2: Kill leftover Metro to avoid port conflicts during build
kill_existing_metro

# Step 3: Backend infrastructure
ensure_backend || exit 1
if [[ -n "$_BACKEND_PID" ]]; then
  _PIDS_TO_KILL+=("$_BACKEND_PID")
fi

# Step 4: Start Metro in background BEFORE builds
# Apps launched by expo run:* connect to Metro immediately on start.
# Metro must be running first, otherwise the dev client shows an error screen.
log "Starting Metro bundler..."
cd "$MOBILE_DIR"
npx expo start --dev-client &
_METRO_PID=$!
_PIDS_TO_KILL+=("$_METRO_PID")

# Wait for Metro to be ready
log "Waiting for Metro to be ready..."
if ! wait_for_url "http://localhost:8081/status" 30 2 "Metro bundler"; then
  exit 1
fi
log "Metro bundler is ready."

# Step 5: Platform-specific build
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

# Step 6: Wait on Metro (foreground)
# NOTE: Do NOT use `exec` here — it replaces the shell process and prevents
# the trap handler from firing, leaving backend API and emulator processes
# running after Ctrl+C. Instead, wait on Metro so that when it exits
# (or user presses Ctrl+C), the EXIT trap fires and cleans up.
wait "$_METRO_PID" 2>/dev/null || true
