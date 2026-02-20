import { streamTurnEvents } from './sse-client';
import { apiClient } from './client';

// Mock the API client
jest.mock('./client', () => ({
  apiClient: {
    postStream: jest.fn(),
  },
}));

const mockPostStream = apiClient.postStream as jest.MockedFunction<
  typeof apiClient.postStream
>;

// Helper to create a mock reader that yields encoded text chunks
function createMockReader(chunks: string[]) {
  const encoder = new TextEncoder();
  let index = 0;

  return {
    read: jest.fn(() => {
      if (index < chunks.length) {
        const value = encoder.encode(chunks[index]);
        index++;
        return Promise.resolve({ done: false, value });
      }
      return Promise.resolve({ done: true, value: undefined });
    }),
  };
}

// Helper to create a mock Response with a body that has a getReader method
function createStreamResponse(
  chunks: string[],
  options: { ok?: boolean; status?: number } = {},
): Response {
  const { ok = true, status = 200 } = options;
  return {
    ok,
    status,
    body: {
      getReader: () => createMockReader(chunks),
    },
    json: jest.fn(() => Promise.resolve(null)),
  } as unknown as Response;
}

// Collect all events from the async generator
async function collectEvents(
  conversationId: string,
  audioData: Blob,
): Promise<Array<{ type: string; data: unknown }>> {
  const events: Array<{ type: string; data: unknown }> = [];
  for await (const event of streamTurnEvents(conversationId, audioData)) {
    events.push(event);
  }
  return events;
}

describe('streamTurnEvents', () => {
  const mockBlob = new Blob(['audio-data']);

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('yields stt_result event', async () => {
    const sseChunks = [
      'event: stt_result\ndata: {"text":"Hello world"}\n\n',
    ];
    mockPostStream.mockResolvedValue(createStreamResponse(sseChunks));

    const events = await collectEvents('conv-1', mockBlob);

    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({
      type: 'stt_result',
      data: { text: 'Hello world' },
    });
  });

  it('yields ai_response_chunk events', async () => {
    const sseChunks = [
      'event: ai_response_chunk\ndata: {"text":"Hi"}\n\n',
      'event: ai_response_chunk\ndata: {"text":" there"}\n\n',
    ];
    mockPostStream.mockResolvedValue(createStreamResponse(sseChunks));

    const events = await collectEvents('conv-1', mockBlob);

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

  it('yields ai_response_done event', async () => {
    const sseChunks = [
      'event: ai_response_done\ndata: {"text":"Hi there, how are you?"}\n\n',
    ];
    mockPostStream.mockResolvedValue(createStreamResponse(sseChunks));

    const events = await collectEvents('conv-1', mockBlob);

    expect(events).toHaveLength(1);
    expect(events[0].type).toBe('ai_response_done');
  });

  it('yields tts_audio_url event', async () => {
    const sseChunks = [
      'event: tts_audio_url\ndata: {"url":"https://storage.example.com/audio.mp3"}\n\n',
    ];
    mockPostStream.mockResolvedValue(createStreamResponse(sseChunks));

    const events = await collectEvents('conv-1', mockBlob);

    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({
      type: 'tts_audio_url',
      data: { url: 'https://storage.example.com/audio.mp3' },
    });
  });

  it('yields correction_result event', async () => {
    const correctionData = {
      turnId: 'turn-1',
      correctedText: 'Hello there',
      explanation: 'Added greeting',
      items: [
        {
          original: 'Hello',
          corrected: 'Hello there',
          originalSentence: 'Hello',
          correctedSentence: 'Hello there',
          type: 'expression',
          explanation: 'More natural greeting',
        },
      ],
    };
    const sseChunks = [
      `event: correction_result\ndata: ${JSON.stringify(correctionData)}\n\n`,
    ];
    mockPostStream.mockResolvedValue(createStreamResponse(sseChunks));

    const events = await collectEvents('conv-1', mockBlob);

    expect(events).toHaveLength(1);
    expect(events[0].type).toBe('correction_result');
    expect(events[0].data).toEqual(correctionData);
  });

  it('yields turn_complete event', async () => {
    const sseChunks = [
      'event: turn_complete\ndata: {}\n\n',
    ];
    mockPostStream.mockResolvedValue(createStreamResponse(sseChunks));

    const events = await collectEvents('conv-1', mockBlob);

    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({ type: 'turn_complete', data: {} });
  });

  it('yields error event from stream', async () => {
    const sseChunks = [
      'event: error\ndata: {"code":"STT_ERROR","message":"Speech recognition failed"}\n\n',
    ];
    mockPostStream.mockResolvedValue(createStreamResponse(sseChunks));

    const events = await collectEvents('conv-1', mockBlob);

    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({
      type: 'error',
      data: { code: 'STT_ERROR', message: 'Speech recognition failed' },
    });
  });

  it('handles multiple events in a single stream chunk', async () => {
    const sseChunks = [
      'event: stt_result\ndata: {"text":"Hello"}\n\n' +
        'event: ai_response_chunk\ndata: {"text":"Hi"}\n\n' +
        'event: ai_response_done\ndata: {"text":"Hi"}\n\n' +
        'event: tts_audio_url\ndata: {"url":"http://audio.mp3"}\n\n' +
        'event: turn_complete\ndata: {}\n\n',
    ];
    mockPostStream.mockResolvedValue(createStreamResponse(sseChunks));

    const events = await collectEvents('conv-1', mockBlob);

    expect(events).toHaveLength(5);
    expect(events.map((e) => e.type)).toEqual([
      'stt_result',
      'ai_response_chunk',
      'ai_response_done',
      'tts_audio_url',
      'turn_complete',
    ]);
  });

  it('handles chunked data split across multiple reads', async () => {
    // The SSE event is split across two network reads
    const sseChunks = [
      'event: stt_result\n',
      'data: {"text":"Hello"}\n\n',
    ];
    mockPostStream.mockResolvedValue(createStreamResponse(sseChunks));

    const events = await collectEvents('conv-1', mockBlob);

    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({
      type: 'stt_result',
      data: { text: 'Hello' },
    });
  });

  it('skips malformed JSON data lines', async () => {
    const sseChunks = [
      'event: stt_result\ndata: {invalid json}\n\n' +
        'event: ai_response_done\ndata: {"text":"Valid"}\n\n',
    ];
    mockPostStream.mockResolvedValue(createStreamResponse(sseChunks));

    const events = await collectEvents('conv-1', mockBlob);

    // The malformed JSON should be skipped, only valid event remains
    expect(events).toHaveLength(1);
    expect(events[0].type).toBe('ai_response_done');
  });

  it('yields error event when response is not ok', async () => {
    const errorResponse = {
      ok: false,
      status: 500,
      json: jest.fn(() =>
        Promise.resolve({
          error: { code: 'SERVER_ERROR', message: 'Internal error' },
        }),
      ),
    } as unknown as Response;
    mockPostStream.mockResolvedValue(errorResponse);

    const events = await collectEvents('conv-1', mockBlob);

    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({
      type: 'error',
      data: { code: 'SERVER_ERROR', message: 'Internal error' },
    });
  });

  it('yields default error when response is not ok and body parse fails', async () => {
    const errorResponse = {
      ok: false,
      status: 500,
      json: jest.fn(() => Promise.reject(new Error('Parse error'))),
    } as unknown as Response;
    mockPostStream.mockResolvedValue(errorResponse);

    const events = await collectEvents('conv-1', mockBlob);

    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({
      type: 'error',
      data: { code: 'STREAM_ERROR', message: 'Failed to start stream' },
    });
  });

  it('sends audio as FormData to the correct endpoint', async () => {
    const sseChunks = ['event: turn_complete\ndata: {}\n\n'];
    mockPostStream.mockResolvedValue(createStreamResponse(sseChunks));

    await collectEvents('conv-123', mockBlob);

    expect(mockPostStream).toHaveBeenCalledTimes(1);
    const [path, formData] = mockPostStream.mock.calls[0];
    expect(path).toBe('/api/conversations/conv-123/turns');
    expect(formData).toBeInstanceOf(FormData);
  });

  it('handles empty stream (no events)', async () => {
    const sseChunks: string[] = [];
    mockPostStream.mockResolvedValue(createStreamResponse(sseChunks));

    const events = await collectEvents('conv-1', mockBlob);

    expect(events).toHaveLength(0);
  });

  it('ignores lines that are not event or data fields', async () => {
    const sseChunks = [
      'id: 123\nevent: stt_result\nretry: 5000\ndata: {"text":"Hello"}\n\n',
    ];
    mockPostStream.mockResolvedValue(createStreamResponse(sseChunks));

    const events = await collectEvents('conv-1', mockBlob);

    expect(events).toHaveLength(1);
    expect(events[0].type).toBe('stt_result');
  });

  it('handles data without a preceding event type (should be ignored)', async () => {
    const sseChunks = [
      'data: {"text":"orphan data"}\n\n' +
        'event: stt_result\ndata: {"text":"Hello"}\n\n',
    ];
    mockPostStream.mockResolvedValue(createStreamResponse(sseChunks));

    const events = await collectEvents('conv-1', mockBlob);

    // The orphan data line has no currentEvent set, so it should be skipped
    expect(events).toHaveLength(1);
    expect(events[0].type).toBe('stt_result');
  });
});
