#!/usr/bin/env bash
# scripts/test/test-claude-hooks.sh — smoke + adversarial test for the
# Claude Code supply-chain hooks (.claude/hooks/check-uv-install.sh and
# .claude/hooks/check-protected-files.sh).
#
# This is a "speed bump" test suite, not a security test suite — the
# adversarial section deliberately covers only the patterns the hooks are
# claimed to catch (per docs/CONTRIB.md). Bypasses via variable expansion,
# string concatenation, PATH shadowing, and similar are KNOWN limitations
# documented in the hook headers and not asserted here.
#
# Run manually or from CI:
#   bash scripts/test/test-claude-hooks.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BASH_HOOK="$REPO_ROOT/.claude/hooks/check-uv-install.sh"
EDIT_HOOK="$REPO_ROOT/.claude/hooks/check-protected-files.sh"

if [[ ! -x "$BASH_HOOK" ]]; then echo "FAIL: $BASH_HOOK not executable" >&2; exit 1; fi
if [[ ! -x "$EDIT_HOOK" ]]; then echo "FAIL: $EDIT_HOOK not executable" >&2; exit 1; fi

fails=0
pass() { echo "  OK  $1"; }
fail() { echo "  FAIL  $1" >&2; fails=$((fails + 1)); }

# -----------------------------------------------------------------------------
# Helpers — feed a JSON payload and capture (stderr, exit code).
# -----------------------------------------------------------------------------

run_bash_hook() {
  local cmd="$1"
  local payload
  payload="$(jq -nc --arg cmd "$cmd" '{tool_input: {command: $cmd}}')"
  set +e
  out="$(printf '%s' "$payload" | bash "$BASH_HOOK" 2>&1)"
  rc=$?
  set -e
}

run_edit_hook() {
  local file="$1"
  local payload
  payload="$(jq -nc --arg f "$file" '{tool_input: {file_path: $f}}')"
  set +e
  out="$(printf '%s' "$payload" | bash "$EDIT_HOOK" 2>&1)"
  rc=$?
  set -e
}

assert_blocked() {
  local label="$1"
  if [[ "$rc" -eq 2 && "$out" == *"BLOCKED"* ]]; then
    pass "$label"
  else
    fail "$label (rc=$rc, out=$out)"
  fi
}

assert_allowed() {
  local label="$1"
  if [[ "$rc" -eq 0 ]]; then
    pass "$label"
  else
    fail "$label (rc=$rc, out=$out)"
  fi
}

# =============================================================================
# Bash hook — direct forbidden commands
# =============================================================================

run_bash_hook "uv pip install httpx"
assert_blocked "block: uv pip install"

run_bash_hook "uv pip compile requirements.in"
assert_blocked "block: uv pip compile"

run_bash_hook "uv pip sync requirements.txt"
assert_blocked "block: uv pip sync"

run_bash_hook "uv pip uninstall httpx"
assert_blocked "block: uv pip uninstall"

run_bash_hook "cd apps/api && uv pip install -e ."
assert_blocked "block: chained uv pip install"

run_bash_hook "uv add httpx"
assert_blocked "block: uv add"

run_bash_hook "uv remove httpx"
assert_blocked "block: uv remove"

run_bash_hook "uv lock"
assert_blocked "block: uv lock"

run_bash_hook "uv lock --upgrade"
assert_blocked "block: uv lock --upgrade"

run_bash_hook "uvx ruff check"
assert_blocked "block: uvx"

run_bash_hook "uv tool install ruff"
assert_blocked "block: uv tool install"

run_bash_hook "uv tool run ruff"
assert_blocked "block: uv tool run"

run_bash_hook "uv tool upgrade ruff"
assert_blocked "block: uv tool upgrade"

run_bash_hook "uv sync"
assert_blocked "block: uv sync without --frozen"

run_bash_hook "uv sync --extra dev"
assert_blocked "block: uv sync --extra dev (no --frozen)"

run_bash_hook "uv sync --refresh # --frozen"
assert_blocked "block: uv sync with --frozen as comment"

run_bash_hook "FOO=--frozen uv sync"
assert_blocked "block: env-var prefix --frozen + uv sync"

run_bash_hook "uv sync --frozen-mode"
assert_blocked "block: uv sync --frozen-mode (not standalone token)"

run_bash_hook "pip install httpx"
assert_blocked "block: pip install"

run_bash_hook "pip3 install httpx"
assert_blocked "block: pip3 install"

run_bash_hook "python -m pip install httpx"
assert_blocked "block: python -m pip install"

run_bash_hook "python3 -m pip install httpx"
assert_blocked "block: python3 -m pip install"

# Backtick command substitution
run_bash_hook 'echo `uv pip install httpx`'
assert_blocked "block: backtick uv pip install"

# =============================================================================
# Bash hook — indirect-execution wrappers (Pattern set 2)
# =============================================================================

run_bash_hook "bash -c 'uv pip install evil'"
assert_blocked "block: bash -c uv pip install"

run_bash_hook "sh -c 'uv pip install evil'"
assert_blocked "block: sh -c uv pip install"

run_bash_hook "bash -c 'uv tool install ruff'"
assert_blocked "block: bash -c uv tool install"

run_bash_hook "bash -c 'pip install evil'"
assert_blocked "block: bash -c pip install"

run_bash_hook "bash -c 'uvx ruff'"
assert_blocked "block: bash -c uvx"

run_bash_hook "eval 'uv pip install evil'"
assert_blocked "block: eval uv pip install"

run_bash_hook 'python -c "import subprocess; subprocess.run([\"uv\",\"pip\",\"install\",\"evil\"])"'
assert_blocked "block: python -c subprocess"

run_bash_hook 'python -c "__import__('"'"'pip'"'"').main([\"install\",\"evil\"])"'
assert_blocked "block: python -c pip __import__"

# =============================================================================
# Bash hook — file mutation against protected files (Pattern set 3)
# =============================================================================

run_bash_hook "chmod -x .claude/hooks/check-uv-install.sh"
assert_blocked "block: chmod -x check-uv-install.sh"

run_bash_hook "chmod 000 scripts/uv-install.sh"
assert_blocked "block: chmod 000 uv-install.sh"

run_bash_hook "rm scripts/uv-install.sh"
assert_blocked "block: rm uv-install.sh"

run_bash_hook "rm -f .claude/hooks/check-protected-files.sh"
assert_blocked "block: rm -f check-protected-files.sh"

run_bash_hook "mv apps/mobile/.npmrc /tmp/x"
assert_blocked "block: mv apps/mobile/.npmrc"

run_bash_hook "cp /tmp/evil scripts/install-npm-pinned.sh"
assert_blocked "block: cp ... install-npm-pinned.sh"

run_bash_hook "sed -i '' 's/exit 2/exit 0/' .claude/hooks/check-uv-install.sh"
assert_blocked "block: sed -i check-uv-install.sh"

run_bash_hook "sed --in-place 's/foo/bar/' scripts/uv-install.sh"
assert_blocked "block: sed --in-place uv-install.sh"

run_bash_hook "ln -sf /dev/null .claude/hooks/check-uv-install.sh"
assert_blocked "block: ln -sf check-uv-install.sh"

run_bash_hook "echo evil > scripts/uv-install.sh"
assert_blocked "block: > redirect to uv-install.sh"

run_bash_hook "echo evil >> apps/mobile/.npmrc"
assert_blocked "block: >> redirect to .npmrc"

run_bash_hook "tee scripts/uv-install.sh < /tmp/x"
assert_blocked "block: tee uv-install.sh"

# Read-only operations on protected files MUST still be allowed.
run_bash_hook "cat scripts/uv-install.sh"
assert_allowed "allow: cat uv-install.sh"

run_bash_hook "grep foo scripts/uv-install.sh"
assert_allowed "allow: grep uv-install.sh"

run_bash_hook "git diff scripts/uv-install.sh"
assert_allowed "allow: git diff uv-install.sh"

# Mutation against an UNPROTECTED file in the same chain should not trigger.
run_bash_hook "rm /tmp/scratch && cat scripts/uv-install.sh"
assert_allowed "allow: rm /tmp + cat protected"

run_bash_hook "echo done > /tmp/x && cat scripts/uv-install.sh"
assert_allowed "allow: > /tmp + cat protected"

# =============================================================================
# Bash hook — sanctioned patterns (must remain allowed)
# =============================================================================

run_bash_hook "make api-lock"
assert_allowed "allow: make api-lock"

run_bash_hook "make api-install"
assert_allowed "allow: make api-install"

run_bash_hook "bash scripts/uv-install.sh lock"
assert_allowed "allow: scripts/uv-install.sh lock"

run_bash_hook "./scripts/install-npm-pinned.sh"
assert_allowed "allow: scripts/install-npm-pinned.sh"

run_bash_hook "uv sync --frozen"
assert_allowed "allow: uv sync --frozen"

run_bash_hook "uv sync --frozen --extra dev"
assert_allowed "allow: uv sync --frozen --extra dev"

run_bash_hook "uv sync --frozen --no-dev"
assert_allowed "allow: uv sync --frozen --no-dev"

run_bash_hook "cd apps/api && uv sync --frozen --extra dev"
assert_allowed "allow: chained uv sync --frozen"

run_bash_hook "uv sync --frozen=true"
assert_allowed "allow: uv sync --frozen=true"

run_bash_hook "uv venv"
assert_allowed "allow: uv venv"

run_bash_hook "uv run pytest"
assert_allowed "allow: uv run pytest"

run_bash_hook "uv --version"
assert_allowed "allow: uv --version"

# Unrelated commands should pass through.
run_bash_hook "ls -la"
assert_allowed "allow: ls"

run_bash_hook "git status"
assert_allowed "allow: git status"

run_bash_hook "echo hello"
assert_allowed "allow: echo"

# Empty / non-Bash payload
out=""
rc=0
set +e
echo '{}' | bash "$BASH_HOOK" >/dev/null 2>&1
rc=$?
set -e
if [[ $rc -eq 0 ]]; then
  pass "allow: empty payload (no command)"
else
  fail "empty payload (rc=$rc)"
fi

# =============================================================================
# Edit/Write/MultiEdit hook — protected files (absolute path)
# =============================================================================

run_edit_hook "/repo/apps/mobile/.npmrc"
assert_blocked "block: edit absolute apps/mobile/.npmrc"

run_edit_hook "/repo/scripts/uv-install.sh"
assert_blocked "block: edit absolute scripts/uv-install.sh"

run_edit_hook "/repo/scripts/install-npm-pinned.sh"
assert_blocked "block: edit absolute scripts/install-npm-pinned.sh"

run_edit_hook "/repo/.claude/hooks/check-uv-install.sh"
assert_blocked "block: edit absolute check-uv-install.sh"

run_edit_hook "/repo/.claude/hooks/check-protected-files.sh"
assert_blocked "block: edit absolute check-protected-files.sh"

# =============================================================================
# Edit/Write/MultiEdit hook — protected files (relative path)
# =============================================================================

run_edit_hook "apps/mobile/.npmrc"
assert_blocked "block: edit relative apps/mobile/.npmrc"

run_edit_hook "scripts/uv-install.sh"
assert_blocked "block: edit relative scripts/uv-install.sh"

run_edit_hook ".claude/hooks/check-uv-install.sh"
assert_blocked "block: edit relative check-uv-install.sh"

# =============================================================================
# Edit/Write/MultiEdit hook — allowed files
# =============================================================================

run_edit_hook "/repo/.claude/settings.json"
assert_allowed "allow: edit .claude/settings.json (intentionally not protected)"

run_edit_hook "/repo/apps/api/src/coyo/main.py"
assert_allowed "allow: edit apps/api source"

run_edit_hook "/repo/apps/api/uv.lock"
assert_allowed "allow: edit uv.lock (regenerated by make api-lock)"

run_edit_hook "/repo/apps/api/pyproject.toml"
assert_allowed "allow: edit pyproject.toml"

run_edit_hook "/repo/README.md"
assert_allowed "allow: edit README.md"

# Empty payload
out=""
rc=0
set +e
echo '{}' | bash "$EDIT_HOOK" >/dev/null 2>&1
rc=$?
set -e
if [[ $rc -eq 0 ]]; then
  pass "allow: empty payload (no file_path)"
else
  fail "empty payload (rc=$rc)"
fi

# -----------------------------------------------------------------------------
# Report
# -----------------------------------------------------------------------------
if (( fails > 0 )); then
  echo "FAILED: $fails test(s)" >&2
  exit 1
fi
echo "All Claude Code hook smoke tests passed."
