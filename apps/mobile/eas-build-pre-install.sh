#!/bin/bash
# EAS Build pre-install hook
# Decodes Base64-encoded Firebase config files from EAS Secrets
# for preview and production builds.
#
# Required EAS Secrets (Base64-encoded):
#   GOOGLE_SERVICES_JSON_BASE64  — google-services.json for Android
#   GOOGLE_SERVICES_PLIST_BASE64 — GoogleService-Info.plist for iOS

set -euo pipefail

FIREBASE_DIR="./firebase/production"

if [ -n "${GOOGLE_SERVICES_JSON_BASE64:-}" ]; then
  echo "Decoding google-services.json from EAS Secret..."
  mkdir -p "$FIREBASE_DIR"
  echo "$GOOGLE_SERVICES_JSON_BASE64" | base64 --decode > "$FIREBASE_DIR/google-services.json"
  chmod 600 "$FIREBASE_DIR/google-services.json"
  if ! python3 -c "import json; json.load(open('$FIREBASE_DIR/google-services.json'))" 2>/dev/null; then
    echo "ERROR: google-services.json is not valid JSON" >&2
    exit 1
  fi
  echo "Written and validated $FIREBASE_DIR/google-services.json"
fi

if [ -n "${GOOGLE_SERVICES_PLIST_BASE64:-}" ]; then
  echo "Decoding GoogleService-Info.plist from EAS Secret..."
  mkdir -p "$FIREBASE_DIR"
  echo "$GOOGLE_SERVICES_PLIST_BASE64" | base64 --decode > "$FIREBASE_DIR/GoogleService-Info.plist"
  chmod 600 "$FIREBASE_DIR/GoogleService-Info.plist"
  if command -v plutil &>/dev/null; then
    if ! plutil -lint "$FIREBASE_DIR/GoogleService-Info.plist" 2>/dev/null; then
      echo "ERROR: GoogleService-Info.plist is not valid plist" >&2
      exit 1
    fi
  fi
  echo "Written and validated $FIREBASE_DIR/GoogleService-Info.plist"
fi
