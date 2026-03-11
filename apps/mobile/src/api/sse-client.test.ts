import { streamTurnEvents, parseSSEResponse, parseSSEBuffer } from './sse-client';

// Mock dependencies
jest.mock('expo-constants', () => ({
  expoConfig: { extra: { apiBaseUrl: 'http://test-api' } },
}));

// Mock expo/fetch
const mockFetch = jest.fn();
jest.mock('expo/fetch', () => ({
  fetch: (...args: unknown[]) => mockFetch(...args),
}));

/**
 * Encode a string as a Uint8Array (simulates what ReadableStream delivers).
 */
function encode(text: string): Uint8Array {
  return new TextEncoder().encode(text);
}

/**
 * Create a ReadableStream that yields the given chunks sequentially.
 * Each chunk simulates a network packet arriving from the server.
 */
function createChunkedStream(chunks: string[]): ReadableStream<Uint8Array> {
  let index = 0;
  return new ReadableStream({
    pull(controller) {
      if (index < chunks.length) {
        controller.enqueue(encode(chunks[index]));
        index++;
      } else {
        controller.close();
      }
    },
  });
}

/**
 * Create a mock response with a ReadableStream body.
 */
function createStreamingResponse(
  chunks: string[],
  options: { ok?: boolean; status?: number } = {},
): Response {
  const { ok = true, status = 200 } = options;
  return {
    ok,
    status,
    body: createChunkedStream(chunks),
    text: jest.fn(() => Promise.resolve(chunks.join(''))),
  } as unknown as Response;
}

/**
 * Create a mock error response (no streaming body needed).
 */
function createErrorResponse(
  body: string,
  options: { status?: number } = {},
): Response {
  const { status = 500 } = options;
  return {
    ok: false,
    status,
    body: null,
    text: jest.fn(() => Promise.resolve(body)),
  } as unknown as Response;
}

// Collect all events from the async generator
async function collectEvents(
  conversationId: string,
  audioFormData: FormData,
  signal?: AbortSignal,
): Promise<Array<{ type: string; data: unknown }>> {
  const events: Array<{ type: string; data: unknown }> = [];
  for await (const event of streamTurnEvents(conversationId, audioFormData, signal)) {
    events.push(event);
  }
  return events;
}

describe('parseSSEBuffer', () => {
  it('parses a single complete event', () => {
    const { events, remaining } = parseSSEBuffer('event: stt_result\ndata: {"text":"Hello"}\n\n');
    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({ type: 'stt_result', data: { text: 'Hello' } });
    expect(remaining).toBe('');
  });

  it('returns remaining buffer when no complete event exists', () => {
    const { events, remaining } = parseSSEBuffer('event: stt_result\ndata: {"text":"partial');
    expect(events).toHaveLength(0);
    expect(remaining).toBe('event: stt_result\ndata: {"text":"partial');
  });

  it('returns empty remaining when buffer ends on event boundary', () => {
    const { events, remaining } = parseSSEBuffer('event: stt_result\ndata: {"text":"Hello"}\n\n');
    expect(events).toHaveLength(1);
    expect(remaining).toBe('');
  });

  it('handles consecutive empty blocks', () => {
    const { events, remaining } = parseSSEBuffer('\n\n\n\nevent: stt_result\ndata: {"text":"Hello"}\n\n');
    expect(events).toHaveLength(1);
    expect(remaining).toBe('');
  });

  it('parses multiple events and keeps remaining', () => {
    const buffer =
      'event: stt_result\ndata: {"text":"Hello"}\n\n' +
      'event: ai_response_done\ndata: {"text":"Hi"}\n\n' +
      'event: turn_complete\ndata: ';
    const { events, remaining } = parseSSEBuffer(buffer);
    expect(events).toHaveLength(2);
    expect(events.map((e) => e.type)).toEqual(['stt_result', 'ai_response_done']);
    expect(remaining).toBe('event: turn_complete\ndata: ');
  });

  it('handles \\r\\n line endings', () => {
    const { events, remaining } = parseSSEBuffer('event: stt_result\r\ndata: {"text":"Hello"}\r\n\r\n');
    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({ type: 'stt_result', data: { text: 'Hello' } });
    expect(remaining).toBe('');
  });

  it('handles \\r line endings', () => {
    const { events, remaining } = parseSSEBuffer('event: stt_result\rdata: {"text":"Hello"}\r\r');
    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({ type: 'stt_result', data: { text: 'Hello' } });
    expect(remaining).toBe('');
  });

  it('skips SSE comment lines', () => {
    const { events } = parseSSEBuffer(': keep-alive\nevent: stt_result\ndata: {"text":"Hello"}\n\n');
    expect(events).toHaveLength(1);
    expect(events[0].type).toBe('stt_result');
  });

  it('skips malformed JSON with dev warning', () => {
    const { events } = parseSSEBuffer('event: stt_result\ndata: {bad}\n\nevent: turn_complete\ndata: {}\n\n');
    expect(events).toHaveLength(1);
    expect(events[0].type).toBe('turn_complete');
  });

  it('returns empty events and empty remaining for empty buffer', () => {
    const { events, remaining } = parseSSEBuffer('');
    expect(events).toHaveLength(0);
    expect(remaining).toBe('');
  });
});

describe('parseSSEResponse', () => {
  it('parses a single event', () => {
    const body = 'event: stt_result\ndata: {"text":"Hello"}\n\n';
    const events = parseSSEResponse(body);
    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({ type: 'stt_result', data: { text: 'Hello' } });
  });

  it('parses multiple events', () => {
    const body =
      'event: stt_result\ndata: {"text":"Hello"}\n\n' +
      'event: ai_response_done\ndata: {"text":"Hi"}\n\n' +
      'event: turn_complete\ndata: {}\n\n';
    const events = parseSSEResponse(body);
    expect(events).toHaveLength(3);
    expect(events.map((e) => e.type)).toEqual([
      'stt_result',
      'ai_response_done',
      'turn_complete',
    ]);
  });

  it('skips malformed JSON', () => {
    const body =
      'event: stt_result\ndata: {bad json}\n\n' +
      'event: ai_response_done\ndata: {"text":"Valid"}\n\n';
    const events = parseSSEResponse(body);
    expect(events).toHaveLength(1);
    expect(events[0].type).toBe('ai_response_done');
  });

  it('skips data without preceding event', () => {
    const body =
      'data: {"text":"orphan"}\n\n' +
      'event: stt_result\ndata: {"text":"Hello"}\n\n';
    const events = parseSSEResponse(body);
    expect(events).toHaveLength(1);
    expect(events[0].type).toBe('stt_result');
  });

  it('ignores non-event/data lines', () => {
    const body = 'id: 123\nevent: stt_result\nretry: 5000\ndata: {"text":"Hello"}\n\n';
    const events = parseSSEResponse(body);
    expect(events).toHaveLength(1);
    expect(events[0].type).toBe('stt_result');
  });

  it('returns empty array for empty body', () => {
    expect(parseSSEResponse('')).toHaveLength(0);
  });

  it('handles body without trailing double-newline', () => {
    const body = 'event: stt_result\ndata: {"text":"Hello"}';
    const events = parseSSEResponse(body);
    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({ type: 'stt_result', data: { text: 'Hello' } });
  });
});

describe('streamTurnEvents', () => {
  const mockFormData = new FormData();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('yields stt_result event from a single chunk', async () => {
    const chunks = ['event: stt_result\ndata: {"text":"Hello world"}\n\n'];
    mockFetch.mockResolvedValue(createStreamingResponse(chunks));

    const events = await collectEvents('conv-1', mockFormData);

    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({
      type: 'stt_result',
      data: { text: 'Hello world' },
    });
  });

  it('yields events incrementally across multiple chunks', async () => {
    const chunks = [
      'event: stt_result\ndata: {"text":"Hello"}\n\n',
      'event: ai_response_done\ndata: {"text":"Hi there"}\n\n',
      'event: turn_complete\ndata: {}\n\n',
    ];
    mockFetch.mockResolvedValue(createStreamingResponse(chunks));

    const events = await collectEvents('conv-1', mockFormData);

    expect(events).toHaveLength(3);
    expect(events.map((e) => e.type)).toEqual([
      'stt_result',
      'ai_response_done',
      'turn_complete',
    ]);
  });

  it('handles event split across chunk boundaries', async () => {
    const chunks = [
      'event: stt_result\ndata: {"tex',
      't":"Hello"}\n\n',
    ];
    mockFetch.mockResolvedValue(createStreamingResponse(chunks));

    const events = await collectEvents('conv-1', mockFormData);

    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({
      type: 'stt_result',
      data: { text: 'Hello' },
    });
  });

  it('yields multiple events from a single chunk', async () => {
    const chunks = [
      'event: stt_result\ndata: {"text":"Hello"}\n\n' +
      'event: ai_response_chunk\ndata: {"text":"Hi"}\n\n' +
      'event: ai_response_chunk\ndata: {"text":" there"}\n\n',
    ];
    mockFetch.mockResolvedValue(createStreamingResponse(chunks));

    const events = await collectEvents('conv-1', mockFormData);

    expect(events).toHaveLength(3);
    expect(events[0].type).toBe('stt_result');
    expect(events[1]).toEqual({ type: 'ai_response_chunk', data: { text: 'Hi' } });
    expect(events[2]).toEqual({ type: 'ai_response_chunk', data: { text: ' there' } });
  });

  it('yields all event types in a full conversation turn', async () => {
    const chunks = [
      'event: stt_result\ndata: {"text":"Hello"}\n\n',
      'event: ai_response_chunk\ndata: {"text":"Hi"}\n\n',
      'event: ai_response_done\ndata: {"text":"Hi there"}\n\n',
      'event: tts_audio_url\ndata: {"url":"http://audio.mp3"}\n\n',
      'event: correction_result\ndata: {"correctedText":"Hello","explanation":"ok","items":[]}\n\n',
      'event: turn_complete\ndata: {}\n\n',
    ];
    mockFetch.mockResolvedValue(createStreamingResponse(chunks));

    const events = await collectEvents('conv-1', mockFormData);

    expect(events).toHaveLength(6);
    expect(events.map((e) => e.type)).toEqual([
      'stt_result',
      'ai_response_chunk',
      'ai_response_done',
      'tts_audio_url',
      'correction_result',
      'turn_complete',
    ]);
  });

  it('yields error event when response is not ok', async () => {
    const errorBody = JSON.stringify({
      error: { message: 'Internal error' },
    });
    mockFetch.mockResolvedValue(createErrorResponse(errorBody, { status: 500 }));

    const events = await collectEvents('conv-1', mockFormData);

    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({
      type: 'error',
      data: { code: 'STREAM_ERROR', message: 'Internal error' },
    });
  });

  it('yields error with detail field from validation error', async () => {
    const errorBody = JSON.stringify({ detail: 'Validation failed' });
    mockFetch.mockResolvedValue(createErrorResponse(errorBody, { status: 422 }));

    const events = await collectEvents('conv-1', mockFormData);

    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({
      type: 'error',
      data: { code: 'STREAM_ERROR', message: 'Validation failed' },
    });
  });

  it('yields default error when body is not JSON', async () => {
    mockFetch.mockResolvedValue(createErrorResponse('Server Error', { status: 500 }));

    const events = await collectEvents('conv-1', mockFormData);

    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({
      type: 'error',
      data: { code: 'STREAM_ERROR', message: 'Stream request failed (HTTP 500)' },
    });
  });

  it('sends request to correct endpoint with correct headers', async () => {
    const chunks = ['event: turn_complete\ndata: {}\n\n'];
    mockFetch.mockResolvedValue(createStreamingResponse(chunks));

    await collectEvents('conv-123', mockFormData);

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toBe('http://test-api/api/conversations/conv-123/turns');
    expect(options.method).toBe('POST');
    expect(options.headers).not.toHaveProperty('X-Device-Id');
    expect(options.headers['Accept']).toBe('text/event-stream');
    expect(options.body).toBeInstanceOf(FormData);
  });

  it('passes AbortSignal to fetch', async () => {
    const chunks = ['event: turn_complete\ndata: {}\n\n'];
    mockFetch.mockResolvedValue(createStreamingResponse(chunks));

    const controller = new AbortController();
    await collectEvents('conv-1', mockFormData, controller.signal);

    const [, options] = mockFetch.mock.calls[0];
    expect(options.signal).toBe(controller.signal);
  });

  it('handles empty stream', async () => {
    const chunks = [''];
    mockFetch.mockResolvedValue(createStreamingResponse(chunks));

    const events = await collectEvents('conv-1', mockFormData);

    expect(events).toHaveLength(0);
  });

  it('yields error event from stream data', async () => {
    const chunks = ['event: error\ndata: {"code":"STT_ERROR","message":"Speech recognition failed"}\n\n'];
    mockFetch.mockResolvedValue(createStreamingResponse(chunks));

    const events = await collectEvents('conv-1', mockFormData);

    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({
      type: 'error',
      data: { code: 'STT_ERROR', message: 'Speech recognition failed' },
    });
  });

  it('falls back to text() when response.body is null', async () => {
    const body = 'event: stt_result\ndata: {"text":"Hello"}\n\nevent: turn_complete\ndata: {}\n\n';
    const response = {
      ok: true,
      status: 200,
      body: null,
      text: jest.fn(() => Promise.resolve(body)),
    } as unknown as Response;
    mockFetch.mockResolvedValue(response);

    const events = await collectEvents('conv-1', mockFormData);

    expect(events).toHaveLength(2);
    expect(events[0].type).toBe('stt_result');
    expect(events[1].type).toBe('turn_complete');
  });

  it('handles remaining buffer after stream ends', async () => {
    const chunks = ['event: stt_result\ndata: {"text":"Hello"}'];
    mockFetch.mockResolvedValue(createStreamingResponse(chunks));

    const events = await collectEvents('conv-1', mockFormData);

    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({
      type: 'stt_result',
      data: { text: 'Hello' },
    });
  });

  it('propagates fetch network errors to the consumer', async () => {
    mockFetch.mockRejectedValue(new TypeError('Network request failed'));

    await expect(collectEvents('conv-1', mockFormData)).rejects.toThrow('Network request failed');
  });

  it('releases reader lock when stream errors mid-read', async () => {
    let callCount = 0;
    const mockReleaseLock = jest.fn();
    const mockReader = {
      read: jest.fn(() => {
        callCount++;
        if (callCount === 1) {
          return Promise.resolve({
            done: false,
            value: encode('event: stt_result\ndata: {"text":"Hello"}\n\n'),
          });
        }
        return Promise.reject(new Error('Connection reset'));
      }),
      releaseLock: mockReleaseLock,
    };

    const response = {
      ok: true,
      status: 200,
      body: { getReader: () => mockReader },
    } as unknown as Response;
    mockFetch.mockResolvedValue(response);

    const events: Array<{ type: string; data: unknown }> = [];
    await expect(async () => {
      for await (const event of streamTurnEvents('conv-1', mockFormData)) {
        events.push(event);
      }
    }).rejects.toThrow('Connection reset');

    expect(events).toHaveLength(1);
    expect(mockReleaseLock).toHaveBeenCalledTimes(1);
  });

  it('encodes conversationId in URL to prevent path traversal', async () => {
    const chunks = ['event: turn_complete\ndata: {}\n\n'];
    mockFetch.mockResolvedValue(createStreamingResponse(chunks));

    await collectEvents('../../admin', mockFormData);

    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe('http://test-api/api/conversations/..%2F..%2Fadmin/turns');
  });
});
