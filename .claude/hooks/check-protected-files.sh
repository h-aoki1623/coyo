#!/usr/bin/env bash
# .claude/hooks/check-protected-files.sh — PreToolUse Edit/Write/MultiEdit hook.
#
# Speed bump that refuses Edit/Write/MultiEdit on the small set of files
# whose contents enforce the supply-chain release-age cooldown. If any of
# these files were silently rewritten through the agent, the wrapper /
# lockfile / hook chain could be neutralised in a single tool call.
#
# Bash-side mutations (chmod, rm, mv, sed -i, ln, output redirection)
# targeting the same files are blocked by the sibling Bash hook
# (.claude/hooks/check-uv-install.sh).
#
# Protected files:
#   apps/mobile/.npmrc                       JS cooldown setting
#   scripts/uv-install.sh                    uv wrapper that injects --exclude-newer
#   scripts/install-npm-pinned.sh            integrity-pinned npm installer
#   .claude/hooks/check-uv-install.sh        Bash sibling hook (self-defense)
#   .claude/hooks/check-protected-files.sh   this hook (self-defense)
#
# Intentionally NOT protected:
#   .claude/settings.json — Claude must be able to evolve its own hook
#                            wiring; this is an explicit project decision
#                            (see PR2 confirmation point 5). The trade-off
#                            is that the hook configuration itself is
#                            considered out of scope for self-defense and
#                            is instead protected by code review on PRs.
#
# To legitimately edit a protected file (e.g., bumping the pinned npm
# version, updating the wrapper for a new uv release), see
# docs/CONTRIB.md "Supply-chain defense" for the session-disable procedure.

set -euo pipefail

# -----------------------------------------------------------------------------
# Fail-CLOSED on any preflight error.
# -----------------------------------------------------------------------------

if ! command -v jq >/dev/null 2>&1; then
  echo "BLOCKED by .claude/hooks/check-protected-files.sh:" >&2
  echo "  jq is not installed; the supply-chain hook cannot inspect the edit." >&2
  echo "  Install jq (brew install jq / apt install jq) or disable the hook." >&2
  exit 2
fi

input="$(cat)"
file="$(jq -r '.tool_input.file_path // .tool_input.path // empty' <<< "$input" 2>/dev/null || true)"
[[ -z "$file" ]] && exit 0  # not a file-bearing tool

# -----------------------------------------------------------------------------
# Try to resolve symlinks (best-effort, portable across macOS and Linux).
# os.path.realpath works on non-existent files too (important for Write).
# If python3 is missing, fall back to the original path — the suffix glob
# below still catches direct edits.
# -----------------------------------------------------------------------------

resolved="$file"
if command -v python3 >/dev/null 2>&1; then
  if r="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$file" 2>/dev/null)"; then
    [[ -n "$r" ]] && resolved="$r"
  fi
fi

# -----------------------------------------------------------------------------
# Match each candidate path against the protected suffix list. Both the
# original input path and the symlink-resolved path are checked, so
# ln-based misdirection is caught.
# -----------------------------------------------------------------------------

is_protected() {
  case "$1" in
    apps/mobile/.npmrc | */apps/mobile/.npmrc \
    | scripts/uv-install.sh | */scripts/uv-install.sh \
    | scripts/install-npm-pinned.sh | */scripts/install-npm-pinned.sh \
    | .claude/hooks/check-uv-install.sh | */.claude/hooks/check-uv-install.sh \
    | .claude/hooks/check-protected-files.sh | */.claude/hooks/check-protected-files.sh)
      return 0
      ;;
  esac
  return 1
}

block() {
  cat >&2 <<EOF
BLOCKED by .claude/hooks/check-protected-files.sh (supply-chain speed bump):
  $1

This file enforces the supply-chain release-age cooldown introduced in
PR1a/1b. Editing it through Claude is disabled to prevent the cooldown
from being silently neutralised.

If this edit is legitimate (e.g., bumping the pinned npm version,
updating the wrapper for a new uv release), see docs/CONTRIB.md
"Supply-chain defense" for the session-disable procedure.
EOF
  exit 2
}

if is_protected "$file"; then
  block "$file"
fi

if [[ "$resolved" != "$file" ]] && is_protected "$resolved"; then
  block "$file → $resolved (resolved through symlink)"
fi

exit 0
