import { ExpoConfig, ConfigContext } from 'expo/config';

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
    deploymentTarget: '16.0',
  },
  android: {
    package: 'to.coyo.app',
    adaptiveIcon: {
      foregroundImage: './assets/icon.png',
      backgroundColor: '#4A90E2',
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
        microphonePermission: 'Allow Coyo to access your microphone for English conversation practice.',
      },
    ],
  ],
  extra: {
    apiBaseUrl: process.env.API_BASE_URL ?? 'http://localhost:8000',
    environment: process.env.APP_ENV ?? 'development',
    e2eMode: process.env.E2E_MODE === 'true',
    eas: {
      projectId: '02a4e9f2-99fa-4744-b12c-b77926090402',
    },
  },
  owner: 'coyo-app',
});
