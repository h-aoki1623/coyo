#!/usr/bin/env bash
# scripts/uv-install.sh — uv wrapper that enforces a release-age cooldown.
#
# Supply-chain defense: dependency resolution must only consider package
# versions that were published at least UV_COOLDOWN_DAYS ago. This window
# gives the wider community time to detect malicious releases (e.g., the
# 2025 axios hijack) before they land in our build.
#
# This script is the SINGLE SUPPORTED ENTRY POINT for any uv command that
# performs dependency resolution. It computes a fresh "now - N days" cutoff
# on every invocation and forwards it to uv via --exclude-newer, placed
# IMMEDIATELY AFTER the subcommand so it cannot be swallowed by a `--`
# positional separator in the user's args.
#
# Allowed subcommands: lock, add, remove, sync, pip
# Everything else (venv, run, --version, ...) must be called with bare `uv`.
#
# Usage:
#   ./scripts/uv-install.sh lock
#   ./scripts/uv-install.sh lock --upgrade
#   ./scripts/uv-install.sh add httpx
#
# Environment overrides:
#   UV_COOLDOWN_DAYS — integer >= 7 (hard floor — the override can only
#                      RAISE the cooldown, never lower it). Default: 7.

set -euo pipefail

# -----------------------------------------------------------------------------
# Policy
# -----------------------------------------------------------------------------

MIN_COOLDOWN_DAYS=7
COOLDOWN_DAYS="${UV_COOLDOWN_DAYS:-$MIN_COOLDOWN_DAYS}"

if ! [[ "$COOLDOWN_DAYS" =~ ^[0-9]+$ ]]; then
  echo "uv-install: UV_COOLDOWN_DAYS must be a non-negative integer (got '$COOLDOWN_DAYS')" >&2
  exit 1
fi

if (( COOLDOWN_DAYS < MIN_COOLDOWN_DAYS )); then
  echo "uv-install: UV_COOLDOWN_DAYS=$COOLDOWN_DAYS is below the policy floor of $MIN_COOLDOWN_DAYS days." >&2
  echo "uv-install: Overrides may only RAISE the cooldown, never lower it." >&2
  exit 1
fi

# -----------------------------------------------------------------------------
# Compute cutoff timestamp — "now - COOLDOWN_DAYS" as RFC 3339 UTC
# macOS ships BSD date; Linux ships GNU date — flag syntax differs.
# -----------------------------------------------------------------------------

if date -u -v-1d +%Y-%m-%dT%H:%M:%SZ >/dev/null 2>&1; then
  CUTOFF=$(date -u -v-"${COOLDOWN_DAYS}"d +%Y-%m-%dT%H:%M:%SZ)   # BSD (macOS)
elif date -u -d '1 day ago' +%Y-%m-%dT%H:%M:%SZ >/dev/null 2>&1; then
  CUTOFF=$(date -u -d "${COOLDOWN_DAYS} days ago" +%Y-%m-%dT%H:%M:%SZ)  # GNU (Linux)
else
  echo "uv-install: unable to compute cutoff date — neither BSD nor GNU date detected" >&2
  exit 1
fi

# -----------------------------------------------------------------------------
# Validate uv is available and report its version for audit trails
# -----------------------------------------------------------------------------

if ! command -v uv >/dev/null 2>&1; then
  echo "uv-install: uv is not installed. Install: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  exit 1
fi

UV_VERSION=$(uv --version 2>&1)

# -----------------------------------------------------------------------------
# Validate the subcommand is in the resolution-command allowlist
# -----------------------------------------------------------------------------

if [[ $# -eq 0 ]]; then
  echo "uv-install: no uv subcommand provided" >&2
  echo "Usage: $0 <lock|add|remove|sync|pip> [args...]" >&2
  exit 2
fi

SUBCMD="$1"
shift

case "$SUBCMD" in
  lock|add|remove|sync|pip)
    ;;
  *)
    echo "uv-install: '$SUBCMD' is not a resolution command." >&2
    echo "uv-install: Allowed: lock, add, remove, sync, pip. Call uv directly for the rest." >&2
    exit 2
    ;;
esac

# -----------------------------------------------------------------------------
# Execute with --exclude-newer placed immediately after the subcommand,
# so user args (including a trailing `--`) cannot displace it.
# -----------------------------------------------------------------------------

echo "uv-install: $UV_VERSION" >&2
echo "uv-install: enforcing --exclude-newer=$CUTOFF (cooldown ${COOLDOWN_DAYS}d)" >&2
exec uv "$SUBCMD" --exclude-newer "$CUTOFF" "$@"
