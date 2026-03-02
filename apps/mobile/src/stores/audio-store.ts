import { create } from 'zustand';

interface AudioState {
  recordingStatus: 'idle' | 'recording' | 'processing';
  playbackStatus: 'idle' | 'playing' | 'loading';
  soundLevel: number;

  // Actions
  setRecordingStatus: (status: AudioState['recordingStatus']) => void;
  setPlaybackStatus: (status: AudioState['playbackStatus']) => void;
  setSoundLevel: (level: number) => void;
  reset: () => void;
}

const initialState = {
  recordingStatus: 'idle' as const,
  playbackStatus: 'idle' as const,
  soundLevel: 0,
};

export const useAudioStore = create<AudioState>((set) => ({
  ...initialState,

  setRecordingStatus: (recordingStatus) => set({ recordingStatus }),
  setPlaybackStatus: (playbackStatus) => set({ playbackStatus }),
  setSoundLevel: (soundLevel) => set({ soundLevel }),
  reset: () => set(initialState),
}));
