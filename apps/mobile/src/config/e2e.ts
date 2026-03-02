import Constants from 'expo-constants';

/**
 * Whether the app is running in E2E test mode.
 * When true, audio recording is bypassed with a pre-recorded test audio file
 * instead of using the device microphone.
 *
 * Activated by setting E2E_MODE=true environment variable before building.
 * Only effective in __DEV__ builds.
 */
export const isE2eMode: boolean =
  __DEV__ && Constants.expoConfig?.extra?.e2eMode === true;
