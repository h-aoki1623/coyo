import { streamTurnEvents, parseSSEResponse } from './sse-client';

// Mock dependencies
jest.mock('expo-constants', () => ({
  expoConfig: { extra: { apiBaseUrl: 'http://test-api' } },
}));

jest.mock('@/services/device-id', () => ({
  getOrCreateDeviceId: jest.fn(() => Promise.resolve('test-device-123')),
}));

// Mock fetch globally
const mockFetch = jest.fn();
global.fetch = mockFetch;

function createMockResponse(
  body: string,
  options: { ok?: boolean; status?: number } = {},
): Response {
  const { ok = true, status = 200 } = options;
  return {
    ok,
    status,
    text: jest.fn(() => Promise.resolve(body)),
  } as unknown as Response;
}

// Collect all events from the async generator
async function collectEvents(
  conversationId: string,
  audioFormData: FormData,
): Promise<Array<{ type: string; data: unknown }>> {
  const events: Array<{ type: string; data: unknown }> = [];
  for await (const event of streamTurnEvents(conversationId, audioFormData)) {
    events.push(event);
  }
  return events;
}

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
});

describe('streamTurnEvents', () => {
  const mockFormData = new FormData();
  mockFormData.append('audio', new Blob(['audio-data']));

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('yields stt_result event', async () => {
    const body = 'event: stt_result\ndata: {"text":"Hello world"}\n\n';
    mockFetch.mockResolvedValue(createMockResponse(body));

    const events = await collectEvents('conv-1', mockFormData);

    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({
      type: 'stt_result',
      data: { text: 'Hello world' },
    });
  });

  it('yields ai_response_chunk events', async () => {
    const body =
      'event: ai_response_chunk\ndata: {"text":"Hi"}\n\n' +
      'event: ai_response_chunk\ndata: {"text":" there"}\n\n';
    mockFetch.mockResolvedValue(createMockResponse(body));

    const events = await collectEvents('conv-1', mockFormData);

    expect(events).toHaveLength(2);
    expect(events[0]).toEqual({
      type: 'ai_response_chunk',
      data: { text: 'Hi' },
    });
    expect(events[1]).toEqual({
      type: 'ai_response_chunk',
      data: { text: ' there' },
    });
  });

  it('yields all event types in a full conversation turn', async () => {
    const body =
      'event: stt_result\ndata: {"text":"Hello"}\n\n' +
      'event: ai_response_chunk\ndata: {"text":"Hi"}\n\n' +
      'event: ai_response_done\ndata: {"text":"Hi there"}\n\n' +
      'event: tts_audio_url\ndata: {"url":"http://audio.mp3"}\n\n' +
      'event: correction_result\ndata: {"correctedText":"Hello","explanation":"ok","items":[]}\n\n' +
      'event: turn_complete\ndata: {}\n\n';
    mockFetch.mockResolvedValue(createMockResponse(body));

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
    mockFetch.mockResolvedValue(createMockResponse(errorBody, { ok: false, status: 500 }));

    const events = await collectEvents('conv-1', mockFormData);

    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({
      type: 'error',
      data: { code: 'STREAM_ERROR', message: 'Internal error' },
    });
  });

  it('yields error with detail field from validation error', async () => {
    const errorBody = JSON.stringify({ detail: 'Validation failed' });
    mockFetch.mockResolvedValue(createMockResponse(errorBody, { ok: false, status: 422 }));

    const events = await collectEvents('conv-1', mockFormData);

    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({
      type: 'error',
      data: { code: 'STREAM_ERROR', message: 'Validation failed' },
    });
  });

  it('yields default error when body is not JSON', async () => {
    mockFetch.mockResolvedValue(createMockResponse('Server Error', { ok: false, status: 500 }));

    const events = await collectEvents('conv-1', mockFormData);

    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({
      type: 'error',
      data: { code: 'STREAM_ERROR', message: 'Stream request failed (HTTP 500)' },
    });
  });

  it('sends request to correct endpoint with correct headers', async () => {
    mockFetch.mockResolvedValue(createMockResponse('event: turn_complete\ndata: {}\n\n'));

    await collectEvents('conv-123', mockFormData);

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toBe('http://test-api/api/conversations/conv-123/turns');
    expect(options.method).toBe('POST');
    expect(options.headers['X-Device-Id']).toBe('test-device-123');
    expect(options.headers['Accept']).toBe('text/event-stream');
    expect(options.body).toBeInstanceOf(FormData);
  });

  it('handles empty response', async () => {
    mockFetch.mockResolvedValue(createMockResponse(''));

    const events = await collectEvents('conv-1', mockFormData);

    expect(events).toHaveLength(0);
  });

  it('yields error event from stream data', async () => {
    const body = 'event: error\ndata: {"code":"STT_ERROR","message":"Speech recognition failed"}\n\n';
    mockFetch.mockResolvedValue(createMockResponse(body));

    const events = await collectEvents('conv-1', mockFormData);

    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({
      type: 'error',
      data: { code: 'STT_ERROR', message: 'Speech recognition failed' },
    });
  });
});
