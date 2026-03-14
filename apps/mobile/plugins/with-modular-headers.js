/**
 * Expo Config Plugin: configures CocoaPods for Firebase with React Native.
 *
 * Sets $RNFirebaseAsStaticFramework = true so RNFBAuth / RNFBApp are
 * built as static frameworks (proper -Swift.h generation).
 *
 * NOTE: This plugin works together with expo-build-properties
 * (ios.useFrameworks = 'static') which adds `use_frameworks! :linkage => :static`
 * to the Podfile globally. That is the official fix for the
 * "'FirebaseAuth/FirebaseAuth-Swift.h' file not found" error on Xcode 16+/17.
 *
 * Individual `pod :modular_headers => true` declarations are intentionally
 * NOT used — the react-native-firebase maintainer explicitly advises against
 * them (see https://github.com/invertase/react-native-firebase/issues/8215).
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
