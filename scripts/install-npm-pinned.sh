#!/usr/bin/env bash
# scripts/install-npm-pinned.sh — integrity-verified global install of npm.
#
# Supply-chain defense: we must not install npm from the registry without
# verifying the tarball matches a hash we pinned at code-review time. A
# registry compromise serving a backdoored npm@11.10.0 would otherwise
# let the attacker disable the min-release-age cooldown before `npm ci`
# ever reads .npmrc.
#
# Pinned version: 11.10.0
# Pinned integrity: SHA-512 from https://registry.npmjs.org/npm/11.10.0
#
# To refresh:
#   curl -s https://registry.npmjs.org/npm/<new-version> \
#     | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['dist']['integrity'])"

set -euo pipefail

NPM_VERSION="11.10.0"
NPM_TARBALL_URL="https://registry.npmjs.org/npm/-/npm-${NPM_VERSION}.tgz"
# sha512-<base64>, matches npm registry dist.integrity format
NPM_INTEGRITY="sha512-i8hE43iSIAMFuYVi8TxsEISdELM4fIza600aLjJ0ankGPLqd0oTPKMJqAcO/QWm307MbSlWGzJcNZ0lGMQgHPA=="

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
TARBALL="$TMP_DIR/npm-${NPM_VERSION}.tgz"

echo "[install-npm-pinned] Downloading $NPM_TARBALL_URL"
curl -sSLf -o "$TARBALL" "$NPM_TARBALL_URL"

echo "[install-npm-pinned] Verifying sha512 against pinned hash"
EXPECTED_B64="${NPM_INTEGRITY#sha512-}"
if command -v openssl >/dev/null 2>&1; then
  ACTUAL_B64="$(openssl dgst -sha512 -binary "$TARBALL" | base64 | tr -d '\n')"
elif command -v shasum >/dev/null 2>&1; then
  # shasum -a 512 emits hex; convert hex -> binary -> base64
  HEX="$(shasum -a 512 "$TARBALL" | awk '{print $1}')"
  ACTUAL_B64="$(printf '%s' "$HEX" | xxd -r -p | base64 | tr -d '\n')"
else
  echo "[install-npm-pinned] ERROR: need openssl or shasum for hash verification" >&2
  exit 1
fi

if [[ "$EXPECTED_B64" != "$ACTUAL_B64" ]]; then
  echo "[install-npm-pinned] ERROR: integrity mismatch for npm@${NPM_VERSION}" >&2
  echo "  expected: $EXPECTED_B64" >&2
  echo "  actual:   $ACTUAL_B64" >&2
  exit 1
fi
echo "[install-npm-pinned] Integrity OK"

echo "[install-npm-pinned] Installing npm@${NPM_VERSION} globally from verified tarball"
npm install -g "$TARBALL"
hash -r 2>/dev/null || true

# Hard-assert the upgrade took effect. `npm install -g` can succeed without
# the new binary becoming active (PATH caching, sandboxed global dirs).
INSTALLED_VERSION="$(npm --version)"
if [[ "$INSTALLED_VERSION" != "$NPM_VERSION"* ]]; then
  echo "[install-npm-pinned] ERROR: npm upgrade did not take effect" >&2
  echo "  expected: ${NPM_VERSION}*" >&2
  echo "  actual:   ${INSTALLED_VERSION}" >&2
  exit 1
fi
echo "[install-npm-pinned] npm ${INSTALLED_VERSION} ready"
