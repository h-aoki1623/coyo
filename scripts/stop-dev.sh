#!/usr/bin/env bash
# stop-dev.sh — Stop dev environment processes (API + Metro + Docker)
#
# Usage:
#   ./scripts/stop-dev.sh          # Stop all dev processes
#   make dev-stop                  # Same, via Makefile
#
# Stops:
#   - Backend API (uvicorn) on port 8000
#   - Metro bundler (Expo) on port 8081
#   - Docker containers (Postgres + Redis)
#
# Safe to run when no processes are running (exits cleanly).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
API_DIR="$REPO_ROOT/apps/api"

# Source shared functions (provides API_PORT, METRO_PORT, kill_port_processes, logging)
source "$REPO_ROOT/scripts/lib/common.sh"
init_log "[stop]"
init_worktree

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

stop_service() {
  local port="$1" label="$2"
  local pids
  pids=$(lsof -ti :"$port" 2>/dev/null || true)
  if [[ -z "$pids" ]]; then
    log "$label: not running."
    return 0
  fi
  kill_port_processes "$port" "$label"
  log "$label stopped."
}

echo ""
stop_service "$API_PORT" "API (uvicorn)"
stop_service "$METRO_PORT" "Metro bundler"

# Stop Docker containers (Postgres + Redis)
# NOTE: `docker compose ps` always prints a header line, so skip it with tail +2
if docker compose -f "$REPO_ROOT/docker-compose.yml" -p "$_COMPOSE_PROJECT" ps --status running 2>/dev/null | tail -n +2 | grep -q .; then
  log "Stopping Docker containers..."
  docker compose -f "$REPO_ROOT/docker-compose.yml" -p "$_COMPOSE_PROJECT" down
  log "Docker containers stopped."
else
  log "Docker containers: not running."
fi

echo ""
log "Dev environment stopped."
