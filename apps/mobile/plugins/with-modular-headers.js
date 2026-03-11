/**
 * Expo Config Plugin: configures CocoaPods for Firebase with React Native.
 *
 * 1. Sets $RNFirebaseAsStaticFramework = true so RNFBAuth / RNFBApp are
 *    built as static frameworks (proper -Swift.h generation).
 * 2. Adds :modular_headers => true on specific Firebase dependency pods
 *    instead of the global use_modular_headers! (which conflicts with
 *    ReactCommon on Xcode 17).
 *
 * NOTE (Xcode 17 workaround):
 * After running `npx expo prebuild`, you must pre-build the FirebaseAuth
 * target to generate FirebaseAuth-Swift.h before the main build:
 *
 *   xcodebuild -project ios/Pods/Pods.xcodeproj -target FirebaseAuth \
 *     -configuration Debug build -quiet
 *   cp ios/build/Debug-iphoneos/FirebaseAuth/Swift\ Compatibility\ Header/FirebaseAuth-Swift.h \
 *     ios/Pods/Headers/Public/FirebaseAuth/
 *   cp ios/build/Debug-iphoneos/FirebaseAuth/Swift\ Compatibility\ Header/FirebaseAuth-Swift.h \
 *     ios/Pods/Headers/Private/FirebaseAuth/
 *
 * The run-e2e.sh script handles this automatically.
 */
const { withDangerousMod } = require('expo/config-plugins');
const fs = require('fs');
const path = require('path');

const FIREBASE_MODULAR_HEADER_PODS = [
  'Firebase',
  'FirebaseAuth',
  'FirebaseCore',
  'FirebaseCoreExtension',
  'FirebaseCoreInternal',
  'FirebaseAuthInterop',
  'FirebaseAppCheckInterop',
  'GoogleUtilities',
  'GTMSessionFetcher',
  'RecaptchaInterop',
];

module.exports = function withModularHeaders(config) {
  return withDangerousMod(config, [
    'ios',
    (config) => {
      const podfilePath = path.join(
        config.modRequest.platformProjectRoot,
        'Podfile',
      );
      let podfile = fs.readFileSync(podfilePath, 'utf-8');

      if (podfile.includes('# [Firebase] modular headers')) {
        return config;
      }

      // Add $RNFirebaseAsStaticFramework before the target block
      podfile = podfile.replace(
        /(target\s+'[^']+'\s+do)/,
        `# [Firebase] Build RNFBAuth/RNFBApp as static frameworks for proper Swift header generation\n$RNFirebaseAsStaticFramework = true\n\n$1`,
      );

      const podDeclarations = FIREBASE_MODULAR_HEADER_PODS.map(
        (name) => `  pod '${name}', :modular_headers => true`,
      ).join('\n');

      // Insert pod declarations inside the target block, after use_react_native!
      podfile = podfile.replace(
        /(use_react_native!\([\s\S]*?\))/,
        `$1\n\n  # [Firebase] modular headers for specific pods only\n${podDeclarations}`,
      );

      fs.writeFileSync(podfilePath, podfile, 'utf-8');
      return config;
    },
  ]);
};
