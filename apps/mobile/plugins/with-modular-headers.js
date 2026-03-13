/**
 * Expo Config Plugin: configures CocoaPods for Firebase with React Native.
 *
 * 1. Sets $RNFirebaseAsStaticFramework = true so RNFBAuth / RNFBApp are
 *    built as static frameworks (proper -Swift.h generation).
 * 2. Adds :modular_headers => true on specific Firebase dependency pods
 *    instead of the global use_modular_headers! (which conflicts with
 *    ReactCommon on Xcode 17).
 * 3. Adds an explicit target dependency from RNFBAuth → FirebaseAuth in
 *    post_install, so Xcode compiles FirebaseAuth first and generates
 *    FirebaseAuth-Swift.h before RNFBAuth needs it. This fixes the
 *    "'FirebaseAuth/FirebaseAuth-Swift.h' file not found" error on
 *    Xcode 16+/17 where ScanDependencies runs before Swift compilation.
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

// Ruby code injected into the Podfile's post_install block.
// Adds an explicit Xcode target dependency: RNFBAuth → FirebaseAuth.
// This forces Xcode to compile FirebaseAuth (generating FirebaseAuth-Swift.h)
// before RNFBAuth attempts to import it.
const SWIFT_HEADER_DEPENDENCY_SNIPPET = `
  # [Firebase] Xcode 16+/17 workaround: explicit target dependency for Swift header
  # RNFBAuth imports <FirebaseAuth/FirebaseAuth-Swift.h>, which is generated when
  # FirebaseAuth's Swift code compiles. Without this dependency, Xcode's
  # ScanDependencies phase may run RNFBAuth before FirebaseAuth finishes.
  rnfb_auth_target = installer.pods_project.targets.find { |t| t.name == 'RNFBAuth' }
  firebase_auth_target = installer.pods_project.targets.find { |t| t.name == 'FirebaseAuth' }
  if rnfb_auth_target && firebase_auth_target
    unless rnfb_auth_target.dependencies.any? { |d| d.target == firebase_auth_target }
      rnfb_auth_target.add_dependency(firebase_auth_target)
    end
  end
`;

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

      // Inject Swift header dependency into post_install block
      podfile = podfile.replace(
        /(post_install\s+do\s+\|installer\|)/,
        `$1\n${SWIFT_HEADER_DEPENDENCY_SNIPPET}`,
      );

      fs.writeFileSync(podfilePath, podfile, 'utf-8');
      return config;
    },
  ]);
};
