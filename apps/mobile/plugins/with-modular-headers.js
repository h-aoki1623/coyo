/**
 * Expo Config Plugin: configures CocoaPods for Firebase with React Native.
 *
 * Sets $RNFirebaseAsStaticFramework = true so RNFBAuth / RNFBApp are
 * built as static frameworks (required by react-native-firebase).
 *
 * This plugin works together with expo-build-properties
 * (ios.useFrameworks = 'static') which adds `use_frameworks! :linkage => :static`
 * to the Podfile globally, as required by the react-native-firebase docs.
 *
 * NOTE: With react-native-firebase v23+ (Firebase iOS SDK 12.x), per-pod
 * `modular_headers` and the fix-firebase-swift-header.sh workaround are no
 * longer needed. The Swift header generation issue that required them was
 * resolved in Firebase iOS SDK 12.x.
 */
const { withDangerousMod } = require('expo/config-plugins');
const fs = require('fs');
const path = require('path');

module.exports = function withModularHeaders(config) {
  return withDangerousMod(config, [
    'ios',
    (config) => {
      const podfilePath = path.join(
        config.modRequest.platformProjectRoot,
        'Podfile',
      );
      let podfile = fs.readFileSync(podfilePath, 'utf-8');

      if (podfile.includes('$RNFirebaseAsStaticFramework')) {
        return config;
      }

      // Add $RNFirebaseAsStaticFramework before the target block
      podfile = podfile.replace(
        /(target\s+'[^']+'\s+do)/,
        `# [Firebase] Build RNFBAuth/RNFBApp as static frameworks\n$RNFirebaseAsStaticFramework = true\n\n$1`,
      );

      fs.writeFileSync(podfilePath, podfile, 'utf-8');
      return config;
    },
  ]);
};
