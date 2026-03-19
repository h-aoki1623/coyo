import { renderHook, act } from '@testing-library/react-native';
import { useTurnStreaming } from '../useTurnStreaming';
import type { TurnEvent } from '@/types/api';

// Mock external dependencies
jest.mock('@/api/sse-client', () => ({
  streamTurnEvents: jest.fn(),
}));

jest.mock('../useAudioRecording', () => ({
  buildAudioFormData: jest.fn(() => new FormData()),
}));

jest.mock('@/stores/conversation-store', () => ({
  useConversationStore: jest.fn((selector: (s: Record<string, unknown>) => unknown) =>
    selector({
      addTurn: jest.fn(),
      updateTurnCorrectionStatus: jest.fn(),
      updateCorrection: jest.fn(),
    }),
  ),
}));

jest.mock('@/stores/audio-store', () => ({
  useAudioStore: jest.fn((selector: (s: Record<string, unknown>) => unknown) =>
    selector({
      setRecordingStatus: jest.fn(),
      setPlaybackStatus: jest.fn(),
    }),
  ),
}));

// Import mocked module to control behavior
import { streamTurnEvents } from '@/api/sse-client';

const mockStreamTurnEvents = streamTurnEvents as jest.MockedFunction<
  typeof streamTurnEvents
>;

/**
 * Helper to create an async iterable from an array of TurnEvents.
 * This simulates the SSE stream that useTurnStreaming consumes.
 */
async function* createMockStream(events: TurnEvent[]): AsyncGenerator<TurnEvent> {
  for (const event of events) {
    yield event;
  }
}

describe('useTurnStreaming - isWebSearching state', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('starts with isWebSearching as false', () => {
    mockStreamTurnEvents.mockReturnValue(createMockStream([]));

    const { result } = renderHook(() =>
      useTurnStreaming('conv-1', 'test-topic'),
    );

    expect(result.current.isWebSearching).toBe(false);
  });

  it('sets isWebSearching to true on web_search_started event', async () => {
    // We need to yield events one at a time to observe intermediate state.
    // Instead, we verify the final state after the stream completes.
    // The web_search_started sets isWebSearching=true, but turn_complete's
    // finally block resets it. So we test indirectly via processEvent logic.

    let resolveSecondEvent: (() => void) | undefined;
    const pausedStream = async function* (): AsyncGenerator<TurnEvent> {
      yield { type: 'stt_result', data: { text: 'Hello' } } as TurnEvent;
      yield { type: 'web_search_started', data: {} } as TurnEvent;
      // Pause here to let us observe isWebSearching = true
      await new Promise<void>((resolve) => {
        resolveSecondEvent = resolve;
      });
      yield { type: 'ai_response_chunk', data: { text: 'Hi' } } as TurnEvent;
      yield { type: 'turn_complete', data: {} } as TurnEvent;
    };

    mockStreamTurnEvents.mockReturnValue(pausedStream());

    const { result } = renderHook(() =>
      useTurnStreaming('conv-1', 'test-topic'),
    );

    // Start processing a turn
    let processPromise: Promise<void>;
    await act(async () => {
      processPromise = result.current.processTurn('file:///audio.m4a');
      // Allow microtasks to process the first two events
      await new Promise((r) => setTimeout(r, 10));
    });

    // After web_search_started, isWebSearching should be true
    expect(result.current.isWebSearching).toBe(true);

    // Resume the stream
    await act(async () => {
      resolveSecondEvent!();
      await processPromise!;
    });

    // After stream completes (finally block), isWebSearching is reset to false
    expect(result.current.isWebSearching).toBe(false);
  });

  it('resets isWebSearching to false on ai_response_chunk event', async () => {
    let resolveAfterChunk: (() => void) | undefined;
    const pausedStream = async function* (): AsyncGenerator<TurnEvent> {
      yield { type: 'stt_result', data: { text: 'Hello' } } as TurnEvent;
      yield { type: 'web_search_started', data: {} } as TurnEvent;
      yield { type: 'ai_response_chunk', data: { text: 'Based on' } } as TurnEvent;
      // Pause to observe that isWebSearching was reset by the chunk
      await new Promise<void>((resolve) => {
        resolveAfterChunk = resolve;
      });
      yield { type: 'turn_complete', data: {} } as TurnEvent;
    };

    mockStreamTurnEvents.mockReturnValue(pausedStream());

    const { result } = renderHook(() =>
      useTurnStreaming('conv-1', 'test-topic'),
    );

    let processPromise: Promise<void>;
    await act(async () => {
      processPromise = result.current.processTurn('file:///audio.m4a');
      await new Promise((r) => setTimeout(r, 10));
    });

    // After ai_response_chunk, isWebSearching should be false
    expect(result.current.isWebSearching).toBe(false);

    // Finish the stream
    await act(async () => {
      resolveAfterChunk!();
      await processPromise!;
    });
  });

  it('resets isWebSearching at the start of a new turn (processTurn)', async () => {
    // First turn: simulate web_search_started without completing
    const firstStream = async function* (): AsyncGenerator<TurnEvent> {
      yield { type: 'stt_result', data: { text: 'Hello' } } as TurnEvent;
      yield { type: 'web_search_started', data: {} } as TurnEvent;
      yield { type: 'ai_response_chunk', data: { text: 'Hi' } } as TurnEvent;
      yield { type: 'turn_complete', data: {} } as TurnEvent;
    };

    mockStreamTurnEvents.mockReturnValue(firstStream());

    const { result } = renderHook(() =>
      useTurnStreaming('conv-1', 'test-topic'),
    );

    // Complete first turn
    await act(async () => {
      await result.current.processTurn('file:///audio.m4a');
    });

    // After first turn, isWebSearching should be false (finally block reset it)
    expect(result.current.isWebSearching).toBe(false);

    // Second turn: verify processTurn resets isWebSearching at the start
    const secondStream = async function* (): AsyncGenerator<TurnEvent> {
      yield { type: 'stt_result', data: { text: 'World' } } as TurnEvent;
      yield { type: 'turn_complete', data: {} } as TurnEvent;
    };

    mockStreamTurnEvents.mockReturnValue(secondStream());

    await act(async () => {
      await result.current.processTurn('file:///audio2.m4a');
    });

    // isWebSearching should be false (was reset at start of processTurn and never set to true)
    expect(result.current.isWebSearching).toBe(false);
  });

  it('resets isWebSearching to false in finally block even on stream error', async () => {
    const errorStream = async function* (): AsyncGenerator<TurnEvent> {
      yield { type: 'stt_result', data: { text: 'Hello' } } as TurnEvent;
      yield { type: 'web_search_started', data: {} } as TurnEvent;
      throw new Error('Network error');
    };

    mockStreamTurnEvents.mockReturnValue(errorStream());

    // Suppress Alert.alert and console.warn during this test
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const alertSpy = jest.spyOn(require('react-native').Alert, 'alert').mockImplementation(() => {});
    const warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});

    const { result } = renderHook(() =>
      useTurnStreaming('conv-1', 'test-topic'),
    );

    await act(async () => {
      await result.current.processTurn('file:///audio.m4a');
    });

    // Even after error, isWebSearching should be reset by finally block
    expect(result.current.isWebSearching).toBe(false);

    alertSpy.mockRestore();
    warnSpy.mockRestore();
  });
});
