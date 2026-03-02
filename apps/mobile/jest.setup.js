// Global native module mocks for Jest

// expo-secure-store
jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn(),
  setItemAsync: jest.fn(),
  deleteItemAsync: jest.fn(),
  AFTER_FIRST_UNLOCK: 'AFTER_FIRST_UNLOCK',
}));

// expo-crypto
jest.mock('expo-crypto', () => ({
  randomUUID: jest.fn(() => 'mock-uuid-1234'),
}));

// expo-av
jest.mock('expo-av', () => ({
  Audio: {
    requestPermissionsAsync: jest.fn(() =>
      Promise.resolve({ status: 'granted' }),
    ),
    setAudioModeAsync: jest.fn(() => Promise.resolve()),
    Recording: jest.fn().mockImplementation(() => ({
      prepareToRecordAsync: jest.fn(() => Promise.resolve()),
      startAsync: jest.fn(() => Promise.resolve()),
      stopAndUnloadAsync: jest.fn(() => Promise.resolve()),
      getURI: jest.fn(() => 'file:///mock-recording.m4a'),
    })),
    Sound: {
      createAsync: jest.fn(() =>
        Promise.resolve({
          sound: {
            unloadAsync: jest.fn(() => Promise.resolve()),
            setOnPlaybackStatusUpdate: jest.fn(),
          },
        }),
      ),
    },
    AndroidOutputFormat: { MPEG_4: 2 },
    AndroidAudioEncoder: { AAC: 3 },
    IOSOutputFormat: { MPEG4AAC: 'aac' },
    IOSAudioQuality: { HIGH: 'high' },
  },
}));

// expo-constants (default export)
jest.mock('expo-constants', () => ({
  __esModule: true,
  default: {
    expoConfig: {
      extra: {
        apiBaseUrl: 'http://localhost:8000',
        e2eMode: false,
      },
    },
  },
}));

// expo-asset
jest.mock('expo-asset', () => ({
  Asset: {
    fromModule: jest.fn(() => ({
      downloadAsync: jest.fn(() => Promise.resolve()),
      localUri: 'file:///mock-test-audio.m4a',
    })),
  },
}));

// @react-native-community/netinfo
jest.mock('@react-native-community/netinfo', () => ({
  addEventListener: jest.fn(() => jest.fn()),
  fetch: jest.fn(() =>
    Promise.resolve({ isConnected: true, isInternetReachable: true }),
  ),
}));

// expo-localization
jest.mock('expo-localization', () => ({
  getLocales: jest.fn(() => [
    { languageCode: 'en', languageTag: 'en-US', regionCode: 'US' },
  ]),
  getCalendars: jest.fn(() => [{}]),
}));

// react-native-safe-area-context
jest.mock('react-native-safe-area-context', () => ({
  SafeAreaView: ({ children }) => children,
  SafeAreaProvider: ({ children }) => children,
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
