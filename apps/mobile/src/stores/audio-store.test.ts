import { useAudioStore } from './audio-store';

// Helper to reset store between tests
function resetStore() {
  useAudioStore.getState().reset();
}

describe('useAudioStore', () => {
  beforeEach(() => {
    resetStore();
  });

  describe('initial state', () => {
    it('has idle recording status', () => {
      expect(useAudioStore.getState().recordingStatus).toBe('idle');
    });

    it('has idle playback status', () => {
      expect(useAudioStore.getState().playbackStatus).toBe('idle');
    });

    it('has zero sound level', () => {
      expect(useAudioStore.getState().soundLevel).toBe(0);
    });
  });

  describe('setRecordingStatus', () => {
    it('sets recording status to recording', () => {
      useAudioStore.getState().setRecordingStatus('recording');
      expect(useAudioStore.getState().recordingStatus).toBe('recording');
    });

    it('sets recording status to processing', () => {
      useAudioStore.getState().setRecordingStatus('processing');
      expect(useAudioStore.getState().recordingStatus).toBe('processing');
    });

    it('sets recording status back to idle', () => {
      useAudioStore.getState().setRecordingStatus('recording');
      useAudioStore.getState().setRecordingStatus('idle');
      expect(useAudioStore.getState().recordingStatus).toBe('idle');
    });

    it('does not affect playback status', () => {
      useAudioStore.getState().setPlaybackStatus('playing');
      useAudioStore.getState().setRecordingStatus('recording');

      expect(useAudioStore.getState().playbackStatus).toBe('playing');
    });
  });

  describe('setPlaybackStatus', () => {
    it('sets playback status to loading', () => {
      useAudioStore.getState().setPlaybackStatus('loading');
      expect(useAudioStore.getState().playbackStatus).toBe('loading');
    });

    it('sets playback status to playing', () => {
      useAudioStore.getState().setPlaybackStatus('playing');
      expect(useAudioStore.getState().playbackStatus).toBe('playing');
    });

    it('sets playback status back to idle', () => {
      useAudioStore.getState().setPlaybackStatus('playing');
      useAudioStore.getState().setPlaybackStatus('idle');
      expect(useAudioStore.getState().playbackStatus).toBe('idle');
    });

    it('does not affect recording status', () => {
      useAudioStore.getState().setRecordingStatus('recording');
      useAudioStore.getState().setPlaybackStatus('playing');

      expect(useAudioStore.getState().recordingStatus).toBe('recording');
    });
  });

  describe('setSoundLevel', () => {
    it('sets sound level to a positive value', () => {
      useAudioStore.getState().setSoundLevel(0.75);
      expect(useAudioStore.getState().soundLevel).toBe(0.75);
    });

    it('sets sound level to zero', () => {
      useAudioStore.getState().setSoundLevel(0.5);
      useAudioStore.getState().setSoundLevel(0);
      expect(useAudioStore.getState().soundLevel).toBe(0);
    });

    it('sets sound level to maximum (1.0)', () => {
      useAudioStore.getState().setSoundLevel(1.0);
      expect(useAudioStore.getState().soundLevel).toBe(1.0);
    });

    it('accepts negative values (metering can produce negatives)', () => {
      useAudioStore.getState().setSoundLevel(-160);
      expect(useAudioStore.getState().soundLevel).toBe(-160);
    });

    it('does not affect other state', () => {
      useAudioStore.getState().setRecordingStatus('recording');
      useAudioStore.getState().setPlaybackStatus('playing');
      useAudioStore.getState().setSoundLevel(0.9);

      expect(useAudioStore.getState().recordingStatus).toBe('recording');
      expect(useAudioStore.getState().playbackStatus).toBe('playing');
    });
  });

  describe('reset', () => {
    it('resets all state to initial values', () => {
      useAudioStore.getState().setRecordingStatus('recording');
      useAudioStore.getState().setPlaybackStatus('playing');
      useAudioStore.getState().setSoundLevel(0.8);

      useAudioStore.getState().reset();

      const state = useAudioStore.getState();
      expect(state.recordingStatus).toBe('idle');
      expect(state.playbackStatus).toBe('idle');
      expect(state.soundLevel).toBe(0);
    });

    it('can set new values after reset', () => {
      useAudioStore.getState().setRecordingStatus('recording');
      useAudioStore.getState().reset();
      useAudioStore.getState().setRecordingStatus('processing');

      expect(useAudioStore.getState().recordingStatus).toBe('processing');
    });
  });
});
