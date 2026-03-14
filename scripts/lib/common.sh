#!/usr/bin/env bash
# common.sh — Shared functions for run-dev.sh and run-e2e.sh
#
# Usage:
#   source "$REPO_ROOT/scripts/lib/common.sh"
#   init_log "[dev]"       # Set log prefix
#   init_worktree          # Set up worktree deps if needed
#
# Callers MUST set these variables before sourcing:
#   REPO_ROOT   — Absolute path to the repository root
#   API_DIR     — Absolute path to apps/api
#
# This file exports:
#   Functions: init_log, log, warn, err, info,
#              init_worktree, kill_existing_metro, ensure_docker,
#              ensure_backend, get_booted_ios_udid, get_android_emulator_id,
#              setup_adb_reverse, boot_ios_simulator, boot_android_emulator,
#              wait_for_url
#   Variables: _MAIN_REPO_ROOT, _COMPOSE_PROJECT, API_PORT, API_HEALTH_URL

# Guard: do nothing if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "This script is meant to be sourced, not executed directly." >&2
  exit 1
fi

# ===========================================================================
# Constants
# ===========================================================================

API_PORT=8000
API_HEALTH_URL="http://localhost:${API_PORT}/health"

# Initialized by init_worktree; callers may read these
_MAIN_REPO_ROOT="$REPO_ROOT"
_COMPOSE_PROJECT="$(basename "$REPO_ROOT")"

# Colors
_CLR_RED='\033[0;31m'
_CLR_GREEN='\033[0;32m'
_CLR_YELLOW='\033[0;33m'
_CLR_CYAN='\033[0;36m'
_CLR_NC='\033[0m'

# ===========================================================================
# Logging
# ===========================================================================

_LOG_PREFIX="[common]"

init_log() {
  _LOG_PREFIX="$1"
}

log()  { echo -e "${_CLR_GREEN}${_LOG_PREFIX}${_CLR_NC} $*"; }
warn() { echo -e "${_CLR_YELLOW}${_LOG_PREFIX}${_CLR_NC} $*"; }
err()  { echo -e "${_CLR_RED}${_LOG_PREFIX}${_CLR_NC} $*" >&2; }
info() { echo -e "${_CLR_CYAN}${_LOG_PREFIX}${_CLR_NC} $*"; }

# ===========================================================================
# Worktree support
# ===========================================================================

init_worktree() {
  source "$REPO_ROOT/scripts/setup-worktree.sh"
  setup_worktree
  _MAIN_REPO_ROOT="$WORKTREE_MAIN_REPO"
  _COMPOSE_PROJECT="$WORKTREE_COMPOSE_PROJECT"
}

# ===========================================================================
# Utility: wait for a URL to respond
# ===========================================================================

# wait_for_url URL MAX_RETRIES SLEEP_SECS LABEL
# Returns 0 on success, 1 on timeout.
wait_for_url() {
  local url="$1" max_retries="$2" sleep_secs="$3" label="$4"
  local retries="$max_retries"
  while ! curl -sf --max-time 2 "$url" > /dev/null 2>&1; do
    retries=$((retries - 1))
    if [[ $retries -le 0 ]]; then
      err "$label did not become ready within $(( max_retries * sleep_secs )) seconds."
      return 1
    fi
    sleep "$sleep_secs"
  done
  return 0
}

# ===========================================================================
# Metro
# ===========================================================================

# Kill any existing Metro process on port 8081
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
        return 1
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
        return 1
      fi
      sleep 2
    done
    log "Docker services are running."
  fi
}

# ===========================================================================
# Backend
# ===========================================================================

# ensure_backend — Start the backend API if not already running.
# On success, sets _BACKEND_PID to the uvicorn PID (empty string if API was
# already running). Callers should use this to manage cleanup.
_BACKEND_PID=""

ensure_backend() {
  _BACKEND_PID=""

  if curl -sf --max-time 3 "$API_HEALTH_URL" > /dev/null 2>&1; then
    log "Backend API already running."
    return 0
  fi

  ensure_docker || return 1

  # Verify venv
  if [[ ! -x "$API_DIR/.venv/bin/python" ]]; then
    err "Python venv not found at $API_DIR/.venv"
    err "Create it with: cd $API_DIR && python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'"
    return 1
  fi

  local venv_python
  venv_python=$("$API_DIR/.venv/bin/python" -c "import sys; print(sys.executable)" 2>/dev/null || true)
  if [[ -z "$venv_python" ]]; then
    err "Python venv is broken. Recreate with: cd $API_DIR && python3 -m venv .venv --clear && .venv/bin/pip install -e '.[dev]'"
    return 1
  fi

  # Run migrations
  # When running in a worktree, the .venv editable install points to the
  # main repo's src/. Override PYTHONPATH so the worktree's src/ takes priority.
  log "Running database migrations..."
  (cd "$API_DIR" && PYTHONPATH="$API_DIR/src:${PYTHONPATH:-}" .venv/bin/alembic upgrade head 2>&1 | tail -3)

  # Start uvicorn in background
  log "Starting backend API..."
  (cd "$API_DIR" && PYTHONPATH="$API_DIR/src:${PYTHONPATH:-}" .venv/bin/uvicorn src.coyo.main:app --port "$API_PORT") &
  _BACKEND_PID=$!

  if ! wait_for_url "$API_HEALTH_URL" 15 2 "Backend API"; then
    kill "$_BACKEND_PID" 2>/dev/null || true
    _BACKEND_PID=""
    return 1
  fi

  log "Backend API is running (PID: $_BACKEND_PID)."
}

# ===========================================================================
# Device detection
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

get_android_emulator_id() {
  adb devices 2>/dev/null | grep -E "emulator-[0-9]+\s+device" | awk '{print $1}' | head -1 || true
}

# ===========================================================================
# iOS Simulator
# ===========================================================================

boot_ios_simulator() {
  local udid
  udid=$(get_booted_ios_udid)
  if [[ -n "$udid" ]]; then
    log "iOS Simulator already booted: $udid"
    return
  fi

  # Pick the first available iPhone simulator (prefer Pro models)
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
    return 1
  fi

  log "Booting iOS Simulator ($target_udid)..."
  xcrun simctl boot "$target_udid" 2>/dev/null || true
  open -a Simulator 2>/dev/null || true
  sleep 3
  log "iOS Simulator booted."
}

# ===========================================================================
# Android Emulator
# ===========================================================================

# boot_android_emulator — Start an Android emulator if none is running.
# Sets _EMULATOR_PID for callers to manage cleanup.
_EMULATOR_PID=""

boot_android_emulator() {
  _EMULATOR_PID=""

  local device_id
  device_id=$(get_android_emulator_id)
  if [[ -n "$device_id" ]]; then
    log "Android Emulator already running: $device_id"
    return
  fi

  if ! command -v adb &>/dev/null; then
    err "adb not found. Install Android SDK platform-tools."
    return 1
  fi

  local avd_name
  avd_name=$("$ANDROID_HOME/emulator/emulator" -list-avds 2>/dev/null | head -1)
  if [[ -z "$avd_name" ]]; then
    err "No Android AVD found. Create one in Android Studio > Virtual Device Manager."
    return 1
  fi

  log "Starting Android Emulator ($avd_name)..."
  "$ANDROID_HOME/emulator/emulator" -avd "$avd_name" -no-snapshot-load &>/dev/null &
  _EMULATOR_PID=$!

  log "Waiting for emulator to boot..."
  local retries=60
  while true; do
    device_id=$(get_android_emulator_id)
    if [[ -n "$device_id" ]]; then
      local boot_status
      boot_status=$(adb -s "$device_id" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r' || true)
      if [[ "$boot_status" == "1" ]]; then
        break
      fi
    fi
    retries=$((retries - 1))
    if [[ $retries -le 0 ]]; then
      err "Android Emulator did not boot within 120 seconds."
      return 1
    fi
    sleep 2
  done
  log "Android Emulator booted: $device_id"
}

# ===========================================================================
# adb reverse
# ===========================================================================

setup_adb_reverse() {
  local device_id="$1"
  adb -s "$device_id" reverse tcp:8081 tcp:8081 2>/dev/null || true
  adb -s "$device_id" reverse tcp:${API_PORT} tcp:${API_PORT} 2>/dev/null || true
  log "adb reverse set up (ports 8081, ${API_PORT})."
}
