#!/bin/bash
# fix-firebase-swift-header.sh
#
# Xcode 17 workaround: pre-builds the FirebaseAuth target from the Pods
# project so that FirebaseAuth-Swift.h is generated, then copies it into
# the Pods headers directory.
#
# Xcode 17's ScanDependencies phase runs before FirebaseAuth compiles its
# Swift code, causing a "FirebaseAuth-Swift.h not found" build error.
# This script must run after `npx expo prebuild` and before `npx expo run:ios`.
#
# Usage:
#   ./scripts/fix-firebase-swift-header.sh
#   # or from repo root:
#   apps/mobile/scripts/fix-firebase-swift-header.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MOBILE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
IOS_DIR="$MOBILE_DIR/ios"
PODS_PROJECT="$IOS_DIR/Pods/Pods.xcodeproj"

if [ ! -d "$PODS_PROJECT" ]; then
  echo "Error: $PODS_PROJECT not found. Run 'npx expo prebuild --platform ios' first."
  exit 1
fi

# Verify FirebaseAuth target exists in the Pods project.
# If Firebase config files (GoogleService-Info.plist) were missing during
# expo prebuild, the Firebase plugins are excluded and this target won't exist.
if ! xcodebuild -project "$PODS_PROJECT" -list 2>/dev/null | grep -q "FirebaseAuth"; then
  echo "[Firebase] Error: FirebaseAuth target not found in Pods project."
  echo ""
  echo "  This usually means Firebase config files were missing during 'expo prebuild'."
  echo "  Verify that the following files exist:"
  echo "    apps/mobile/firebase/development/GoogleService-Info.plist"
  echo "    apps/mobile/firebase/development/google-services.json"
  echo ""
  echo "  To fix:"
  echo "    1. Place the Firebase config files in apps/mobile/firebase/development/"
  echo "    2. Delete the ios/ directory: rm -rf ios/"
  echo "    3. Re-run: npx expo prebuild --platform ios --clean"
  exit 1
fi

echo "[Firebase] Building FirebaseAuth target to generate -Swift.h ..."
xcodebuild \
  -project "$PODS_PROJECT" \
  -target FirebaseAuth \
  -configuration Debug \
  build \
  -quiet 2>/dev/null || true

SWIFT_H=$(find "$IOS_DIR/build" -name "FirebaseAuth-Swift.h" \
  -not -path "*/Pods/Headers/*" 2>/dev/null | head -1)

if [ -z "$SWIFT_H" ] || [ ! -f "$SWIFT_H" ]; then
  echo "[Firebase] Error: FirebaseAuth-Swift.h was not generated."
  echo ""
  echo "  The FirebaseAuth target exists but the Swift header build failed."
  echo "  Check xcodebuild output for details."
  exit 1
fi

for DIR in "Headers/Public/FirebaseAuth" "Headers/Private/FirebaseAuth"; do
  DEST="$IOS_DIR/Pods/$DIR/FirebaseAuth-Swift.h"
  mkdir -p "$(dirname "$DEST")"
  cp "$SWIFT_H" "$DEST"
done

echo "[Firebase] Copied FirebaseAuth-Swift.h to Pods headers"
