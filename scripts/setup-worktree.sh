#!/usr/bin/env bash
# setup-worktree.sh — Copy gitignored dependencies into a git worktree
#
# When running inside a git worktree, gitignored files (node_modules, .venv,
# .env, Firebase configs, etc.) are not present. This script copies them from
# the main repo so the worktree can build and run independently.
#
# Usage:
#   source scripts/setup-worktree.sh   # From run-dev.sh / run-e2e.sh
#   ./scripts/setup-worktree.sh        # Standalone
#
# Behavior:
#   - Detects if running inside a worktree; exits early if not
#   - Copies .env files and credential files from the main repo (skip if exists)
#   - Installs node_modules via `npm ci` (fast with cache)
#   - Creates .venv and installs Python deps
#   - Sets WORKTREE_MAIN_REPO and WORKTREE_COMPOSE_PROJECT for callers
#
# Design decisions:
#   - COPY, not symlink: worktree can freely modify deps (e.g., npm install
#     a new package) without affecting the main repo
#   - npm ci / pip install: derived artifacts are regenerated from lock files,
#     so "losing" them on worktree cleanup is fine
#   - Existing files are never overwritten (protect manual edits)

set -euo pipefail

_WT_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_WT_REPO_ROOT="$(cd "$_WT_SCRIPT_DIR/.." && pwd)"

# Export for callers (run-dev.sh, run-e2e.sh)
WORKTREE_MAIN_REPO="$_WT_REPO_ROOT"
WORKTREE_COMPOSE_PROJECT="$(basename "$_WT_REPO_ROOT")"

_wt_log()  { echo -e "\033[0;32m[worktree]\033[0m $*"; }
_wt_warn() { echo -e "\033[0;33m[worktree]\033[0m $*"; }
_wt_err()  { echo -e "\033[0;31m[worktree]\033[0m $*" >&2; }

# ---------------------------------------------------------------------------
# Detect worktree
# ---------------------------------------------------------------------------

_detect_worktree() {
  local main_repo
  main_repo="$(git -C "$_WT_REPO_ROOT" worktree list --porcelain | head -1 | sed 's/^worktree //')"

  if [[ "$main_repo" == "$_WT_REPO_ROOT" ]]; then
    # Not in a worktree — nothing to do
    return 1
  fi

  WORKTREE_MAIN_REPO="$main_repo"
  WORKTREE_COMPOSE_PROJECT="$(basename "$main_repo")"
  return 0
}

# ---------------------------------------------------------------------------
# Copy a single file from main repo to worktree (skip if already exists)
# ---------------------------------------------------------------------------

_copy_file() {
  local rel_path="$1"
  local src="$WORKTREE_MAIN_REPO/$rel_path"
  local dst="$_WT_REPO_ROOT/$rel_path"

  if [[ -f "$dst" ]]; then
    return  # Already exists — don't overwrite
  fi

  # Remove broken symlink if present (from old symlink-based setup)
  if [[ -L "$dst" ]]; then
    _wt_warn "Removing broken symlink: $rel_path"
    rm "$dst"
  fi

  if [[ ! -f "$src" ]]; then
    _wt_warn "Not found in main repo (skipping): $rel_path"
    return
  fi

  mkdir -p "$(dirname "$dst")"
  cp "$src" "$dst"
  _wt_log "Copied: $rel_path"
}

# ---------------------------------------------------------------------------
# Install node_modules (npm ci with global cache)
# ---------------------------------------------------------------------------

_setup_node_modules() {
  local mobile_dir="$_WT_REPO_ROOT/apps/mobile"

  # Remove broken symlink from old setup
  if [[ -L "$mobile_dir/node_modules" && ! -d "$mobile_dir/node_modules" ]]; then
    _wt_warn "Removing broken node_modules symlink."
    rm "$mobile_dir/node_modules"
  fi

  # Remove symlink in favor of real install
  if [[ -L "$mobile_dir/node_modules" ]]; then
    _wt_warn "Replacing node_modules symlink with independent install."
    rm "$mobile_dir/node_modules"
  fi

  if [[ -d "$mobile_dir/node_modules" ]]; then
    return  # Already installed
  fi

  _wt_log "Installing node_modules (npm ci)..."
  cd "$mobile_dir" && npm ci
  _wt_log "node_modules installed."
}

# ---------------------------------------------------------------------------
# Create .venv and install Python deps
# ---------------------------------------------------------------------------

_setup_venv() {
  local api_dir="$_WT_REPO_ROOT/apps/api"

  # Remove broken symlink from old setup
  if [[ -L "$api_dir/.venv" && ! -d "$api_dir/.venv" ]]; then
    _wt_warn "Removing broken .venv symlink."
    rm "$api_dir/.venv"
  fi

  # Remove symlink in favor of real venv
  if [[ -L "$api_dir/.venv" ]]; then
    _wt_warn "Replacing .venv symlink with independent venv."
    rm "$api_dir/.venv"
  fi

  if [[ -d "$api_dir/.venv" ]]; then
    # Verify venv is not broken (shebang path mismatch)
    local venv_python
    venv_python=$("$api_dir/.venv/bin/python" -c "import sys; print(sys.executable)" 2>/dev/null || true)
    if [[ -n "$venv_python" ]]; then
      return  # Healthy venv exists
    fi
    _wt_warn ".venv exists but is broken. Recreating..."
    rm -rf "$api_dir/.venv"
  fi

  _wt_log "Creating Python venv and installing dependencies..."
  cd "$api_dir"
  python3 -m venv .venv
  .venv/bin/pip install -e '.[dev]' 2>&1 | tail -3
  _wt_log ".venv created."
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

setup_worktree() {
  if ! _detect_worktree; then
    return  # Not in a worktree — nothing to do
  fi

  _wt_log "Detected worktree. Main repo: $WORKTREE_MAIN_REPO"

  # --- Environment files ---
  _copy_file ".env"
  _copy_file "apps/api/.env"
  _copy_file "apps/mobile/.env"

  # --- Firebase / Google credentials ---
  _copy_file "apps/api/firebase-service-account.json"
  _copy_file "apps/mobile/GoogleService-Info.plist"
  _copy_file "apps/mobile/google-services.json"

  # --- Dependencies (install, not copy) ---
  _setup_node_modules
  _setup_venv

  _wt_log "Worktree setup complete."
}

# Run if executed directly (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  setup_worktree
fi
