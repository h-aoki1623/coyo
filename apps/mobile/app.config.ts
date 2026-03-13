import fs from 'fs';
import path from 'path';

import 'dotenv/config';
import type { ExpoConfig, ConfigContext } from 'expo/config';

const FIREBASE_DIR_MAP: Record<string, string> = {
  development: 'development',
  staging: 'production',
  production: 'production',
};
const appEnv = process.env.APP_ENV ?? 'development';
const firebaseDir = `./firebase/${FIREBASE_DIR_MAP[appEnv] ?? 'development'}`;
const FALLBACK_DIR = './firebase/development';

// On EAS Build, Firebase config files are not in the git repo (gitignored).
// They are provided as Base64-encoded EAS Secrets. This function decodes them
// to disk at config evaluation time — before resolveFirebaseConfig() runs —
// so that googleServicesFile paths resolve correctly during both the local
// pre-check (`npx expo config`) and the remote prebuild step.
function decodeFirebaseSecretsIfNeeded(): void {
  const secrets: Array<{ envVar: string; filename: string }> = [
    { envVar: 'GOOGLE_SERVICES_JSON_BASE64', filename: 'google-services.json' },
    { envVar: 'GOOGLE_SERVICES_PLIST_BASE64', filename: 'GoogleService-Info.plist' },
  ];

  for (const { envVar, filename } of secrets) {
    const base64Value = process.env[envVar];
    if (!base64Value) continue;

    const targetPath = path.join(firebaseDir, filename);
    if (fs.existsSync(targetPath)) continue;

    fs.mkdirSync(firebaseDir, { recursive: true });
    fs.writeFileSync(targetPath, Buffer.from(base64Value, 'base64'), { mode: 0o600 });
  }
}

decodeFirebaseSecretsIfNeeded();

function resolveFirebaseConfig(filename: string): string {
  const primary = `${firebaseDir}/${filename}`;
  if (fs.existsSync(primary)) return primary;
  return `${FALLBACK_DIR}/${filename}`;
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
    [
      'expo-build-properties',
      {
        ios: {
          useFrameworks: 'static',
        },
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
