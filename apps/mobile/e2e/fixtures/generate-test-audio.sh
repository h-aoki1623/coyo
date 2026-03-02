#!/usr/bin/env bash
# generate-test-audio.sh — Generate test audio files for E2E voice tests
#
# Uses macOS text-to-speech to create M4A audio files
# containing English speech that the backend STT can process.
#
# Usage:
#   ./e2e/fixtures/generate-test-audio.sh
#
# Prerequisites:
#   - macOS (uses `say` command)
#
# Output:
#   e2e/fixtures/test-audio-clean.m4a   (correct English — no corrections expected)
#   e2e/fixtures/test-audio-errors.m4a  (grammar errors — corrections expected)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if ! command -v say &>/dev/null; then
  echo "Error: 'say' command not found. This script requires macOS."
  exit 1
fi

# Clean audio (correct English)
CLEAN_FILE="$SCRIPT_DIR/test-audio-clean.m4a"
if [[ -f "$CLEAN_FILE" ]]; then
  echo "Clean audio already exists: $CLEAN_FILE"
else
  echo "Generating clean audio..."
  say -o "$CLEAN_FILE" --data-format=aac \
    "Hello, I would like to talk about sports today."
  echo "Generated: $CLEAN_FILE ($(wc -c < "$CLEAN_FILE" | tr -d ' ') bytes)"
fi

# Error audio (intentional grammar mistakes for correction testing)
ERRORS_FILE="$SCRIPT_DIR/test-audio-errors.m4a"
if [[ -f "$ERRORS_FILE" ]]; then
  echo "Error audio already exists: $ERRORS_FILE"
else
  echo "Generating error audio..."
  say -o "$ERRORS_FILE" --data-format=aac \
    "Yesterday I go to the park and I seen many bird. It was very beauty."
  echo "Generated: $ERRORS_FILE ($(wc -c < "$ERRORS_FILE" | tr -d ' ') bytes)"
fi
