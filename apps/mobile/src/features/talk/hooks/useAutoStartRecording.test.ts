import { renderHook, act } from '@testing-library/react-native';
import { useRef, useEffect, useCallback } from 'react';

import { useAudioStore } from '@/stores/audio-store';

/**
 * Extracted auto-start recording logic from TalkScreen for testability.
 * This hook replicates the exact useEffect from TalkScreen lines 246-254.
 */
function useAutoStartRecording({
  canRecord,
  isRecording,
  onStartRecording,
}: {
  canRecord: boolean;
  isRecording: boolean;
  onStartRecording: () => void;
}) {
  const playbackStatus = useAudioStore((s) => s.playbackStatus);
  const prevPlaybackStatusRef = useRef<'idle' | 'playing' | 'loading'>('idle');

  const stableOnStartRecording = useCallback(onStartRecording, [onStartRecording]);

  useEffect(() => {
    const wasPlaying = prevPlaybackStatusRef.current === 'playing';
    prevPlaybackStatusRef.current = playbackStatus;

    if (wasPlaying && playbackStatus === 'idle' && canRecord && !isRecording) {
      stableOnStartRecording();
    }
  }, [playbackStatus, canRecord, isRecording, stableOnStartRecording]);
}

describe('useAutoStartRecording', () => {
  beforeEach(() => {
    useAudioStore.getState().reset();
  });

  it('auto-starts recording when playback transitions from playing to idle and canRecord is true', () => {
    const onStartRecording = jest.fn();

    // Set playback to playing before rendering
    useAudioStore.getState().setPlaybackStatus('playing');

    renderHook(
      ({ canRecord, isRecording }) =>
        useAutoStartRecording({ canRecord, isRecording, onStartRecording }),
      { initialProps: { canRecord: true, isRecording: false } },
    );

    // On mount, prevRef is 'idle' and playbackStatus is 'playing' -> no match (wasPlaying=false)
    expect(onStartRecording).not.toHaveBeenCalled();

    // Now transition playback from playing to idle
    act(() => {
      useAudioStore.getState().setPlaybackStatus('idle');
    });

    expect(onStartRecording).toHaveBeenCalledTimes(1);
  });

  it('does not auto-start when playback stays idle (no transition)', () => {
    const onStartRecording = jest.fn();

    // Playback starts idle (default)
    renderHook(() =>
      useAutoStartRecording({
        canRecord: true,
        isRecording: false,
        onStartRecording,
      }),
    );

    // Set idle again explicitly
    act(() => {
      useAudioStore.getState().setPlaybackStatus('idle');
    });

    expect(onStartRecording).not.toHaveBeenCalled();
  });

  it('does not auto-start on initial mount when playbackStatus is idle', () => {
    const onStartRecording = jest.fn();

    // Default state: playbackStatus = 'idle', prevRef = 'idle'
    renderHook(() =>
      useAutoStartRecording({
        canRecord: true,
        isRecording: false,
        onStartRecording,
      }),
    );

    expect(onStartRecording).not.toHaveBeenCalled();
  });

  it('does not auto-start when canRecord is false (isStreaming)', () => {
    const onStartRecording = jest.fn();

    useAudioStore.getState().setPlaybackStatus('playing');

    renderHook(() =>
      useAutoStartRecording({
        canRecord: false,
        isRecording: false,
        onStartRecording,
      }),
    );

    act(() => {
      useAudioStore.getState().setPlaybackStatus('idle');
    });

    expect(onStartRecording).not.toHaveBeenCalled();
  });

  it('does not auto-start when already recording', () => {
    const onStartRecording = jest.fn();

    useAudioStore.getState().setPlaybackStatus('playing');

    renderHook(() =>
      useAutoStartRecording({
        canRecord: true,
        isRecording: true,
        onStartRecording,
      }),
    );

    act(() => {
      useAudioStore.getState().setPlaybackStatus('idle');
    });

    expect(onStartRecording).not.toHaveBeenCalled();
  });

  it('does not auto-start when playback transitions from loading to idle', () => {
    const onStartRecording = jest.fn();

    useAudioStore.getState().setPlaybackStatus('loading');

    renderHook(() =>
      useAutoStartRecording({
        canRecord: true,
        isRecording: false,
        onStartRecording,
      }),
    );

    act(() => {
      useAudioStore.getState().setPlaybackStatus('idle');
    });

    expect(onStartRecording).not.toHaveBeenCalled();
  });

  it('auto-starts after full lifecycle: idle -> playing -> idle', () => {
    const onStartRecording = jest.fn();

    // Start with idle (default)
    renderHook(() =>
      useAutoStartRecording({
        canRecord: true,
        isRecording: false,
        onStartRecording,
      }),
    );

    // Transition to playing
    act(() => {
      useAudioStore.getState().setPlaybackStatus('playing');
    });

    expect(onStartRecording).not.toHaveBeenCalled();

    // Transition to idle -> should trigger
    act(() => {
      useAudioStore.getState().setPlaybackStatus('idle');
    });

    expect(onStartRecording).toHaveBeenCalledTimes(1);
  });

  it('auto-starts multiple times on repeated playing -> idle transitions', () => {
    const onStartRecording = jest.fn();

    renderHook(() =>
      useAutoStartRecording({
        canRecord: true,
        isRecording: false,
        onStartRecording,
      }),
    );

    // First cycle: playing -> idle
    act(() => {
      useAudioStore.getState().setPlaybackStatus('playing');
    });
    act(() => {
      useAudioStore.getState().setPlaybackStatus('idle');
    });

    expect(onStartRecording).toHaveBeenCalledTimes(1);

    // Second cycle: playing -> idle
    act(() => {
      useAudioStore.getState().setPlaybackStatus('playing');
    });
    act(() => {
      useAudioStore.getState().setPlaybackStatus('idle');
    });

    expect(onStartRecording).toHaveBeenCalledTimes(2);
  });

  it('does not auto-start when canRecord becomes false between playing and idle', () => {
    const onStartRecording = jest.fn();

    useAudioStore.getState().setPlaybackStatus('playing');

    const { rerender } = renderHook(
      ({ canRecord, isRecording }) =>
        useAutoStartRecording({ canRecord, isRecording, onStartRecording }),
      { initialProps: { canRecord: true, isRecording: false } },
    );

    // canRecord becomes false (e.g., conversation ended)
    rerender({ canRecord: false, isRecording: false });

    // Playback transitions to idle, but canRecord is false
    act(() => {
      useAudioStore.getState().setPlaybackStatus('idle');
    });

    expect(onStartRecording).not.toHaveBeenCalled();
  });

  it('does not auto-start when playback goes playing -> loading -> idle', () => {
    const onStartRecording = jest.fn();

    renderHook(() =>
      useAutoStartRecording({
        canRecord: true,
        isRecording: false,
        onStartRecording,
      }),
    );

    // playing
    act(() => {
      useAudioStore.getState().setPlaybackStatus('playing');
    });

    // loading (interrupts the playing state)
    act(() => {
      useAudioStore.getState().setPlaybackStatus('loading');
    });

    // idle (previous was loading, not playing)
    act(() => {
      useAudioStore.getState().setPlaybackStatus('idle');
    });

    expect(onStartRecording).not.toHaveBeenCalled();
  });
});
