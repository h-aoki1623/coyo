import 'dotenv/config';
import type { ExpoConfig, ConfigContext } from 'expo/config';

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
    googleServicesFile: process.env.GOOGLE_SERVICES_PLIST ?? './GoogleService-Info.plist',
    infoPlist: {
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
    googleServicesFile: process.env.GOOGLE_SERVICES_JSON ?? './google-services.json',
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
