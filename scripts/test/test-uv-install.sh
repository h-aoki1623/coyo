#!/usr/bin/env bash
# scripts/test/test-uv-install.sh — smoke test for scripts/uv-install.sh
#
# Verifies the wrapper's safety properties:
#   - Rejects missing / unknown / disallowed subcommands
#   - Rejects non-numeric or below-floor UV_COOLDOWN_DAYS
#   - Emits the expected --exclude-newer cutoff for the default cooldown
#   - Allows raising the cooldown via UV_COOLDOWN_DAYS
#
# Run manually or from CI:
#   bash scripts/test/test-uv-install.sh
#
# Exits 0 on success, 1 on any failure. No external test framework.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRAPPER="$SCRIPT_DIR/../uv-install.sh"

if [[ ! -x "$WRAPPER" ]]; then
  echo "FAIL: wrapper not executable at $WRAPPER" >&2
  exit 1
fi

fails=0
pass() { echo "  OK  $1"; }
fail() { echo "  FAIL  $1" >&2; fails=$((fails + 1)); }

# -----------------------------------------------------------------------------
# T1: no subcommand → exit 2 with usage
# -----------------------------------------------------------------------------
set +e
out=$("$WRAPPER" 2>&1)
rc=$?
set -e
if [[ $rc -eq 2 && "$out" == *"no uv subcommand"* ]]; then
  pass "no args exits 2 with usage"
else
  fail "no args (rc=$rc, out=$out)"
fi

# -----------------------------------------------------------------------------
# T2: disallowed subcommand → exit 2
# -----------------------------------------------------------------------------
set +e
out=$("$WRAPPER" venv 2>&1)
rc=$?
set -e
if [[ $rc -eq 2 && "$out" == *"not a resolution command"* ]]; then
  pass "disallowed subcommand (venv) rejected"
else
  fail "disallowed subcommand (rc=$rc, out=$out)"
fi

# -----------------------------------------------------------------------------
# T3: UV_COOLDOWN_DAYS below floor → exit 1
# -----------------------------------------------------------------------------
set +e
out=$(UV_COOLDOWN_DAYS=0 "$WRAPPER" lock 2>&1)
rc=$?
set -e
if [[ $rc -eq 1 && "$out" == *"below the policy floor"* ]]; then
  pass "UV_COOLDOWN_DAYS=0 rejected"
else
  fail "UV_COOLDOWN_DAYS=0 (rc=$rc, out=$out)"
fi

# -----------------------------------------------------------------------------
# T4: UV_COOLDOWN_DAYS non-numeric → exit 1
# -----------------------------------------------------------------------------
set +e
out=$(UV_COOLDOWN_DAYS=abc "$WRAPPER" lock 2>&1)
rc=$?
set -e
if [[ $rc -eq 1 && "$out" == *"non-negative integer"* ]]; then
  pass "UV_COOLDOWN_DAYS=abc rejected"
else
  fail "UV_COOLDOWN_DAYS=abc (rc=$rc, out=$out)"
fi

# -----------------------------------------------------------------------------
# T5: default cooldown (7d) logged on allowed subcommand
# -----------------------------------------------------------------------------
# Use `lock --help` so the wrapper runs to the exec step but uv exits cleanly.
set +e
out=$("$WRAPPER" lock --help 2>&1 >/dev/null)
rc=$?
set -e
if [[ $rc -eq 0 && "$out" == *"enforcing --exclude-newer="* && "$out" == *"cooldown 7d"* ]]; then
  pass "default cooldown (7d) is logged"
else
  fail "default cooldown logging (rc=$rc, out=$out)"
fi

# -----------------------------------------------------------------------------
# T6: UV_COOLDOWN_DAYS=14 raises the cooldown
# -----------------------------------------------------------------------------
set +e
out=$(UV_COOLDOWN_DAYS=14 "$WRAPPER" lock --help 2>&1 >/dev/null)
rc=$?
set -e
if [[ $rc -eq 0 && "$out" == *"cooldown 14d"* ]]; then
  pass "UV_COOLDOWN_DAYS=14 raises the cooldown"
else
  fail "UV_COOLDOWN_DAYS=14 (rc=$rc, out=$out)"
fi

# -----------------------------------------------------------------------------
# Report
# -----------------------------------------------------------------------------
if (( fails > 0 )); then
  echo "FAILED: $fails test(s)" >&2
  exit 1
fi
echo "All uv-install.sh smoke tests passed."
