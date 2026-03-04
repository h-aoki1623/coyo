import { ExpoConfig, ConfigContext } from 'expo/config';

export default ({ config }: ConfigContext): ExpoConfig => ({
  ...config,
  name: 'Coto',
  slug: 'coto',
  version: '0.1.0',
  orientation: 'portrait',
  scheme: 'coto',
  newArchEnabled: true,
  ios: {
    bundleIdentifier: 'com.coto.app',
    supportsTablet: false,
    deploymentTarget: '16.0',
  },
  android: {
    package: 'com.coto.app',
    adaptiveIcon: {
      backgroundColor: '#ffffff',
    },
    minSdkVersion: 29,
    targetSdkVersion: 35,
  },
  plugins: [
    'expo-secure-store',
    'expo-font',
    'expo-localization',
    [
      'expo-av',
      {
        microphonePermission: 'Allow Coto to access your microphone for English conversation practice.',
      },
    ],
  ],
  extra: {
    apiBaseUrl: process.env.API_BASE_URL ?? 'http://localhost:8000',
    environment: process.env.APP_ENV ?? 'development',
    e2eMode: process.env.E2E_MODE === 'true',
    eas: {
      projectId: process.env.EAS_PROJECT_ID ?? '',
    },
  },
  owner: process.env.EXPO_OWNER ?? undefined,
});
