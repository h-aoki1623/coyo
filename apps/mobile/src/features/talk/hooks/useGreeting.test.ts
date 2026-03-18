import { renderHook, act, waitFor } from '@testing-library/react-native';

import { useConversationStore } from '@/stores/conversation-store';
import { useAudioStore } from '@/stores/audio-store';
import { useGreeting } from './useGreeting';
import type { TurnEvent } from '@/types/api';

// Mock expo-av (already in jest.setup.js, but we need fine control)
jest.mock('expo-av', () => ({
  Audio: {
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
  },
}));

// Mock streamGreetingEvents
const mockStreamGreetingEvents = jest.fn();
jest.mock('@/api/sse-client', () => ({
  streamGreetingEvents: (...args: unknown[]) => mockStreamGreetingEvents(...args),
}));

/**
 * Create an async generator from an array of TurnEvents.
 * Simulates the SSE stream from the backend.
 */
async function* createEventStream(events: TurnEvent[]): AsyncGenerator<TurnEvent> {
  for (const event of events) {
    yield event;
  }
}

/**
 * Create an async generator that throws an error after yielding some events.
 */
async function* createErrorStream(
  events: TurnEvent[],
  error: Error,
): AsyncGenerator<TurnEvent> {
  for (const event of events) {
    yield event;
  }
  throw error;
}

describe('useGreeting', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useConversationStore.getState().reset();
    useAudioStore.getState().reset();
  });

  it('calls streamGreetingEvents with correct params', async () => {
    mockStreamGreetingEvents.mockReturnValue(createEventStream([
      { type: 'turn_complete', data: {} },
    ]));

    const { result } = renderHook(() => useGreeting('conv-123', 'sports'));

    await act(async () => {
      await result.current.triggerGreeting();
    });

    expect(mockStreamGreetingEvents).toHaveBeenCalledTimes(1);
    expect(mockStreamGreetingEvents).toHaveBeenCalledWith(
      'conv-123',
      'sports',
      undefined,
    );
  });

  it('passes abort signal to streamGreetingEvents', async () => {
    mockStreamGreetingEvents.mockReturnValue(createEventStream([
      { type: 'turn_complete', data: {} },
    ]));

    const { result } = renderHook(() => useGreeting('conv-123', 'sports'));

    const controller = new AbortController();
    await act(async () => {
      await result.current.triggerGreeting(controller.signal);
    });

    expect(mockStreamGreetingEvents).toHaveBeenCalledWith(
      'conv-123',
      'sports',
      controller.signal,
    );
  });

  it('buffers ai_response_chunk text', async () => {
    mockStreamGreetingEvents.mockReturnValue(createEventStream([
      { type: 'ai_response_chunk', data: { text: 'Hello' } },
      { type: 'ai_response_chunk', data: { text: ' world' } },
      { type: 'tts_audio_url', data: { url: 'http://audio.mp3' } },
      { type: 'turn_complete', data: {} },
    ]));

    const { result } = renderHook(() => useGreeting('conv-123', 'sports'));

    await act(async () => {
      await result.current.triggerGreeting();
    });

    // The AI turn should be added with the full buffered text
    const turns = useConversationStore.getState().turns;
    expect(turns).toHaveLength(1);
    expect(turns[0].role).toBe('ai');
    // After ai_response_done is not sent, chunks are buffered,
    // but turn gets replaced text from chunks
    expect(turns[0].text).toBe('Hello world');
  });

  it('replaces buffered text on ai_response_done', async () => {
    mockStreamGreetingEvents.mockReturnValue(createEventStream([
      { type: 'ai_response_chunk', data: { text: 'Hello' } },
      { type: 'ai_response_chunk', data: { text: ' world' } },
      { type: 'ai_response_done', data: { text: 'Hello world!' } },
      { type: 'tts_audio_url', data: { url: 'http://audio.mp3' } },
      { type: 'turn_complete', data: {} },
    ]));

    const { result } = renderHook(() => useGreeting('conv-123', 'sports'));

    await act(async () => {
      await result.current.triggerGreeting();
    });

    const turns = useConversationStore.getState().turns;
    expect(turns).toHaveLength(1);
    // ai_response_done overrides the buffered text
    expect(turns[0].text).toBe('Hello world!');
  });

  it('adds AI turn to store on tts_audio_url event', async () => {
    mockStreamGreetingEvents.mockReturnValue(createEventStream([
      { type: 'ai_response_chunk', data: { text: 'Hi!' } },
      { type: 'ai_response_done', data: { text: 'Hi!' } },
      { type: 'tts_audio_url', data: { url: 'http://audio.mp3' } },
      { type: 'turn_complete', data: {} },
    ]));

    const { result } = renderHook(() => useGreeting('conv-123', 'sports'));

    await act(async () => {
      await result.current.triggerGreeting();
    });

    const turns = useConversationStore.getState().turns;
    expect(turns).toHaveLength(1);
    expect(turns[0].role).toBe('ai');
    expect(turns[0].text).toBe('Hi!');
    expect(turns[0].conversationId).toBe('conv-123');
    expect(turns[0].sequence).toBe(1);
    expect(turns[0].correctionStatus).toBe('none');
  });

  it('adds AI turn on turn_complete as fallback when no tts_audio_url', async () => {
    mockStreamGreetingEvents.mockReturnValue(createEventStream([
      { type: 'ai_response_chunk', data: { text: 'Hi!' } },
      { type: 'ai_response_done', data: { text: 'Hi!' } },
      { type: 'turn_complete', data: {} },
    ]));

    const { result } = renderHook(() => useGreeting('conv-123', 'sports'));

    await act(async () => {
      await result.current.triggerGreeting();
    });

    const turns = useConversationStore.getState().turns;
    expect(turns).toHaveLength(1);
    expect(turns[0].text).toBe('Hi!');
  });

  it('does not add duplicate turns when both tts_audio_url and turn_complete arrive', async () => {
    mockStreamGreetingEvents.mockReturnValue(createEventStream([
      { type: 'ai_response_chunk', data: { text: 'Hi!' } },
      { type: 'tts_audio_url', data: { url: 'http://audio.mp3' } },
      { type: 'turn_complete', data: {} },
    ]));

    const { result } = renderHook(() => useGreeting('conv-123', 'sports'));

    await act(async () => {
      await result.current.triggerGreeting();
    });

    // addBufferedAiTurn has a guard to prevent duplicate adds
    const turns = useConversationStore.getState().turns;
    expect(turns).toHaveLength(1);
  });

  it('catches AbortError silently without adding error turns', async () => {
    const abortError = new Error('Aborted');
    abortError.name = 'AbortError';

    mockStreamGreetingEvents.mockReturnValue(
      createErrorStream([], abortError),
    );

    const { result } = renderHook(() => useGreeting('conv-123', 'sports'));

    // Should not throw
    await act(async () => {
      await result.current.triggerGreeting();
    });

    const turns = useConversationStore.getState().turns;
    expect(turns).toHaveLength(0);
  });

  it('adds buffered turn on non-abort error as fallback', async () => {
    const networkError = new Error('Network error');
    networkError.name = 'TypeError';

    mockStreamGreetingEvents.mockReturnValue(
      createErrorStream(
        [{ type: 'ai_response_chunk', data: { text: 'Partial' } }],
        networkError,
      ),
    );

    const { result } = renderHook(() => useGreeting('conv-123', 'sports'));

    await act(async () => {
      await result.current.triggerGreeting();
    });

    const turns = useConversationStore.getState().turns;
    expect(turns).toHaveLength(1);
    expect(turns[0].text).toBe('Partial');
  });

  it('sets isGreetingLoading true during greeting and false after', async () => {
    let resolveStream: () => void;
    const streamPromise = new Promise<void>((resolve) => {
      resolveStream = resolve;
    });

    async function* delayedStream(): AsyncGenerator<TurnEvent> {
      yield { type: 'ai_response_chunk', data: { text: 'Hi' } };
      await streamPromise;
      yield { type: 'turn_complete', data: {} as Record<string, never> };
    }

    mockStreamGreetingEvents.mockReturnValue(delayedStream());

    const { result } = renderHook(() => useGreeting('conv-123', 'sports'));

    expect(result.current.isGreetingLoading).toBe(false);

    let triggerPromise: Promise<void>;
    act(() => {
      triggerPromise = result.current.triggerGreeting();
    });

    // After starting, loading should be true
    await waitFor(() => {
      expect(result.current.isGreetingLoading).toBe(true);
    });

    // Resolve the stream
    await act(async () => {
      resolveStream!();
      await triggerPromise!;
    });

    expect(result.current.isGreetingLoading).toBe(false);
  });

  it('resets buffered text on each triggerGreeting call', async () => {
    // First call
    mockStreamGreetingEvents.mockReturnValueOnce(createEventStream([
      { type: 'ai_response_chunk', data: { text: 'First' } },
      { type: 'turn_complete', data: {} },
    ]));

    const { result } = renderHook(() => useGreeting('conv-123', 'sports'));

    await act(async () => {
      await result.current.triggerGreeting();
    });

    // Second call - should not accumulate text from first call
    mockStreamGreetingEvents.mockReturnValueOnce(createEventStream([
      { type: 'ai_response_chunk', data: { text: 'Second' } },
      { type: 'turn_complete', data: {} },
    ]));

    await act(async () => {
      await result.current.triggerGreeting();
    });

    const turns = useConversationStore.getState().turns;
    // Both calls add turns, the second one should have 'Second' not 'FirstSecond'
    const secondTurn = turns[turns.length - 1];
    expect(secondTurn.text).toBe('Second');
  });

  it('adds turn on error event with buffered text', async () => {
    mockStreamGreetingEvents.mockReturnValue(createEventStream([
      { type: 'ai_response_chunk', data: { text: 'Partial text' } },
      { type: 'error', data: { code: 'GREETING_ERROR', message: 'Failed' } },
    ]));

    const { result } = renderHook(() => useGreeting('conv-123', 'sports'));

    await act(async () => {
      await result.current.triggerGreeting();
    });

    const turns = useConversationStore.getState().turns;
    expect(turns).toHaveLength(1);
    expect(turns[0].text).toBe('Partial text');
  });

  it('does not add turn when no text was buffered and error occurs', async () => {
    mockStreamGreetingEvents.mockReturnValue(createEventStream([
      { type: 'error', data: { code: 'GREETING_ERROR', message: 'Failed' } },
    ]));

    const { result } = renderHook(() => useGreeting('conv-123', 'sports'));

    await act(async () => {
      await result.current.triggerGreeting();
    });

    const turns = useConversationStore.getState().turns;
    expect(turns).toHaveLength(0);
  });
});
