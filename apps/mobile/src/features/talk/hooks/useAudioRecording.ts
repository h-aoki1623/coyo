import { useRef, useCallback } from 'react';
import { Alert } from 'react-native';
import { Audio } from 'expo-av';
import { Asset } from 'expo-asset';
import { File as ExpoFile } from 'expo-file-system/next';
import { useAudioStore } from '@/stores/audio-store';
import { isE2eMode } from '@/config/e2e';
import { t } from '@/i18n';

interface UseAudioRecordingReturn {
  startRecording: () => Promise<void>;
  stopRecording: () => Promise<string | null>;
}

const RECORDING_OPTIONS: Audio.RecordingOptions = {
  isMeteringEnabled: true,
  android: {
    extension: '.m4a',
    outputFormat: Audio.AndroidOutputFormat.MPEG_4,
    audioEncoder: Audio.AndroidAudioEncoder.AAC,
    sampleRate: 44100,
    numberOfChannels: 1,
    bitRate: 128000,
  },
  ios: {
    extension: '.m4a',
    outputFormat: Audio.IOSOutputFormat.MPEG4AAC,
    audioQuality: Audio.IOSAudioQuality.HIGH,
    sampleRate: 44100,
    numberOfChannels: 1,
    bitRate: 128000,
    linearPCMBitDepth: 16,
    linearPCMIsBigEndian: false,
    linearPCMIsFloat: false,
  },
  web: {
    mimeType: 'audio/webm',
    bitsPerSecond: 128000,
  },
};

// E2E test audio assets — only bundled in dev builds.
// Clean audio first (no corrections), then error audio (has corrections).
/* eslint-disable @typescript-eslint/no-require-imports */
const testAudioModules: number[] = __DEV__
  ? [
      require('../../../../e2e/fixtures/test-audio-clean.m4a'),
      require('../../../../e2e/fixtures/test-audio-errors.m4a'),
    ]
  : [];
/* eslint-enable @typescript-eslint/no-require-imports */

/**
 * Resolve a test audio file URI from the bundled asset.
 * Downloads the asset to a local cache directory and returns its file:// URI.
 */
async function resolveTestAudioUri(moduleId: number): Promise<string | null> {
  const asset = Asset.fromModule(moduleId);
  await asset.downloadAsync();
  return asset.localUri ?? null;
}

/**
 * Hook for managing audio recording with expo-av.
 * Handles permission requests and recording lifecycle.
 *
 * In E2E mode (E2E_MODE=true), recording is bypassed:
 * - startRecording sets the UI to "recording" state without using the microphone
 * - stopRecording returns a pre-recorded test audio file URI
 */
export function useAudioRecording(): UseAudioRecordingReturn {
  const recordingRef = useRef<Audio.Recording | null>(null);
  const e2eTurnIndexRef = useRef(0);
  const setRecordingStatus = useAudioStore((s) => s.setRecordingStatus);

  const requestPermission = useCallback(async (): Promise<boolean> => {
    const { status } = await Audio.requestPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert(
        t('errors.micPermissionTitle'),
        t('errors.micPermissionMessage'),
      );
      return false;
    }
    return true;
  }, []);

  const startRecording = useCallback(async () => {
    // E2E mode: skip mic permission and actual recording
    if (isE2eMode) {
      setRecordingStatus('recording');
      return;
    }

    const hasPermission = await requestPermission();
    if (!hasPermission) return;

    try {
      // Configure audio mode for recording
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
        staysActiveInBackground: false,
        shouldDuckAndroid: true,
        playThroughEarpieceAndroid: false,
      });

      const recording = new Audio.Recording();
      await recording.prepareToRecordAsync(RECORDING_OPTIONS);
      await recording.startAsync();

      recordingRef.current = recording;
      setRecordingStatus('recording');
    } catch {
      Alert.alert(t('errors.genericError'), t('errors.recordingError'));
      setRecordingStatus('idle');
    }
  }, [requestPermission, setRecordingStatus]);

  const stopRecording = useCallback(async (): Promise<string | null> => {
    // E2E mode: return the next bundled test audio file (cycles through array)
    if (isE2eMode && testAudioModules.length > 0) {
      setRecordingStatus('processing');
      const index = e2eTurnIndexRef.current % testAudioModules.length;
      e2eTurnIndexRef.current++;
      const uri = await resolveTestAudioUri(testAudioModules[index]);
      return uri;
    }

    const recording = recordingRef.current;
    if (!recording) return null;

    try {
      setRecordingStatus('processing');
      await recording.stopAndUnloadAsync();

      // Reset audio mode for playback
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: false,
        playsInSilentModeIOS: true,
        staysActiveInBackground: false,
        shouldDuckAndroid: true,
        playThroughEarpieceAndroid: false,
      });

      const uri = recording.getURI();
      recordingRef.current = null;
      return uri;
    } catch {
      setRecordingStatus('idle');
      recordingRef.current = null;
      return null;
    }
  }, [setRecordingStatus]);

  return { startRecording, stopRecording };
}

/**
 * Build a FormData object from a recording file URI.
 *
 * Uses expo-file-system/next's File class which produces a native FileBlob
 * compatible with expo/fetch. The React Native {uri, type, name} pattern
 * only works with native fetch but fails with expo/fetch, and JS-layer
 * Blob objects (via atob + Uint8Array) are not serializable by expo/fetch's
 * native implementation either.
 */
export function buildAudioFormData(uri: string): FormData {
  const file = new ExpoFile(uri);
  const formData = new FormData();
  formData.append('audio', file.blob(), file.name);
  return formData;
}
