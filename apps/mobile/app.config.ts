import fs from 'fs';

import 'dotenv/config';
import type { ExpoConfig, ConfigContext } from 'expo/config';

const FIREBASE_DIR_MAP: Record<string, string> = {
  development: 'development',
  staging: 'production',
  production: 'production',
};
const appEnv = process.env.APP_ENV ?? 'development';
const firebaseDir = `./firebase/${FIREBASE_DIR_MAP[appEnv] ?? 'development'}`;

// On EAS Build, production Firebase configs are decoded by eas-build-pre-install.sh
// before prebuild runs. However, EAS CLI also evaluates this config locally
// (via `npx expo config`) before uploading the project, at which point
// production files do not exist. Return undefined so the local pre-check
// does not fail with ENOENT. The config plugin mods that actually require the
// file only run during prebuild on the remote builder, where the file exists.
function resolveFirebaseConfig(filename: string): string | undefined {
  const primary = `${firebaseDir}/${filename}`;
  if (fs.existsSync(primary)) return primary;
  return undefined;
}

export default ({ config }: ConfigContext): ExpoConfig => ({
  ...config,
  name: 'Coyo',
  slug: 'coyo',
  version: '0.1.0',
  orientation: 'portrait',
  icon: './assets/icon.png',
  scheme: 'coyo',
  newArchEnabled: true,
  ios: {
    bundleIdentifier: 'to.coyo.app',
    supportsTablet: false,
    googleServicesFile: process.env.GOOGLE_SERVICES_PLIST ?? resolveFirebaseConfig('GoogleService-Info.plist'),
    infoPlist: {
      ITSAppUsesNonExemptEncryption: false,
      GIDClientID: process.env.GID_CLIENT_ID ?? '',
    },
    entitlements: {
      'com.apple.developer.applesignin': ['Default'],
    },
  },
  android: {
    package: 'to.coyo.app',
    adaptiveIcon: {
      foregroundImage: './assets/icon.png',
      backgroundColor: '#4A90E2',
    },
    googleServicesFile: process.env.GOOGLE_SERVICES_JSON ?? resolveFirebaseConfig('google-services.json'),
  },
  plugins: [
    'expo-secure-store',
    'expo-font',
    'expo-localization',
    [
      'expo-av',
      {
        microphonePermission: 'Allow Coyo to access your microphone for English conversation practice.',
      },
    ],
    '@react-native-firebase/app',
    '@react-native-firebase/auth',
    '@react-native-google-signin/google-signin',
    './plugins/with-modular-headers',
  ],
  extra: {
    apiBaseUrl: process.env.API_BASE_URL ?? 'http://localhost:8000',
    environment: process.env.APP_ENV ?? 'development',
    e2eMode: process.env.E2E_MODE === 'true',
    googleWebClientId: process.env.GOOGLE_WEB_CLIENT_ID ?? '',
    eas: {
      projectId: '02a4e9f2-99fa-4744-b12c-b77926090402',
    },
  },
  owner: 'coyo-app',
});
