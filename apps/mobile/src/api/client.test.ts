import { apiClient } from './client';

// Store original fetch
const originalFetch = global.fetch;

// Helper to create a mock Response
function createMockResponse(
  body: unknown,
  options: { status?: number; ok?: boolean } = {},
): Response {
  const { status = 200, ok = true } = options;
  return {
    ok,
    status,
    json: jest.fn(() => Promise.resolve(body)),
    headers: new Headers(),
    body: null,
    bodyUsed: false,
    redirected: false,
    statusText: ok ? 'OK' : 'Error',
    type: 'basic' as ResponseType,
    url: '',
    clone: jest.fn(),
    arrayBuffer: jest.fn(),
    blob: jest.fn(),
    formData: jest.fn(),
    text: jest.fn(),
    bytes: jest.fn(),
  } as unknown as Response;
}

describe('apiClient', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = jest.fn();
  });

  afterAll(() => {
    global.fetch = originalFetch;
  });

  describe('get', () => {
    it('sends a GET request with correct headers', async () => {
      const mockData = { items: [] };
      (global.fetch as jest.Mock).mockResolvedValue(
        createMockResponse(mockData),
      );

      await apiClient.get('/api/test');

      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/test',
        expect.objectContaining({
          headers: {
            'Content-Type': 'application/json',
          },
        }),
      );
    });

    it('returns data on successful response', async () => {
      const mockData = { id: '1', name: 'Test' };
      (global.fetch as jest.Mock).mockResolvedValue(
        createMockResponse(mockData),
      );

      const result = await apiClient.get<{ id: string; name: string }>(
        '/api/test',
      );

      expect(result).toEqual({ data: { id: '1', name: 'Test' } });
    });

    it('returns error envelope on non-ok response with error body', async () => {
      const errorBody = {
        error: { code: 'NOT_FOUND', message: 'Resource not found' },
      };
      (global.fetch as jest.Mock).mockResolvedValue(
        createMockResponse(errorBody, { status: 404, ok: false }),
      );

      const result = await apiClient.get('/api/missing');

      expect(result).toEqual({
        error: { code: 'NOT_FOUND', message: 'Resource not found' },
      });
    });

    it('returns generic error when response body is not parseable', async () => {
      const response = {
        ok: false,
        status: 500,
        json: jest.fn(() => Promise.reject(new Error('Invalid JSON'))),
      } as unknown as Response;
      (global.fetch as jest.Mock).mockResolvedValue(response);

      const result = await apiClient.get('/api/broken');

      expect(result).toEqual({
        error: {
          code: 'UNKNOWN_ERROR',
          message: 'Request failed with status 500',
        },
      });
    });

    it('does not include X-Device-Id header', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(
        createMockResponse({ ok: true }),
      );

      await apiClient.get('/api/test');

      const callArgs = (global.fetch as jest.Mock).mock.calls[0];
      expect(callArgs[1].headers).not.toHaveProperty('X-Device-Id');
    });
  });

  describe('post', () => {
    it('sends a POST request with JSON body', async () => {
      const requestBody = { topic: 'sports' };
      const responseData = { conversationId: 'conv-1' };
      (global.fetch as jest.Mock).mockResolvedValue(
        createMockResponse(responseData),
      );

      const result = await apiClient.post('/api/conversations', requestBody);

      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/conversations',
        expect.objectContaining({
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(requestBody),
        }),
      );
      expect(result).toEqual({ data: responseData });
    });

    it('sends a POST request without body when body is undefined', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(
        createMockResponse({ ok: true }),
      );

      await apiClient.post('/api/action');

      const callArgs = (global.fetch as jest.Mock).mock.calls[0];
      expect(callArgs[1].body).toBeUndefined();
    });

    it('returns error envelope on failure', async () => {
      const errorBody = {
        error: { code: 'VALIDATION_ERROR', message: 'Invalid input' },
      };
      (global.fetch as jest.Mock).mockResolvedValue(
        createMockResponse(errorBody, { status: 400, ok: false }),
      );

      const result = await apiClient.post('/api/test', { invalid: true });

      expect(result).toEqual({
        error: { code: 'VALIDATION_ERROR', message: 'Invalid input' },
      });
    });
  });

  describe('delete', () => {
    it('sends a DELETE request with correct headers', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(
        createMockResponse(null),
      );

      await apiClient.delete('/api/conversations/conv-1');

      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/conversations/conv-1',
        expect.objectContaining({
          method: 'DELETE',
          headers: {
            'Content-Type': 'application/json',
          },
        }),
      );
    });

    it('returns ApiResponse with data', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(
        createMockResponse(null),
      );

      const result = await apiClient.delete('/api/test/1');

      expect(result).toEqual({ data: null });
    });
  });

  describe('postStream', () => {
    it('sends a POST request with FormData and no device ID header', async () => {
      const mockFormData = new FormData();
      mockFormData.append('audio', 'blob-data');

      const mockResponse = createMockResponse(null);
      (global.fetch as jest.Mock).mockResolvedValue(mockResponse);

      const result = await apiClient.postStream(
        '/api/conversations/conv-1/turns',
        mockFormData,
      );

      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/conversations/conv-1/turns',
        {
          method: 'POST',
          headers: {},
          body: mockFormData,
        },
      );
      expect(result).toBe(mockResponse);
    });

    it('does not include Content-Type header (let browser set multipart boundary)', async () => {
      const mockFormData = new FormData();
      (global.fetch as jest.Mock).mockResolvedValue(
        createMockResponse(null),
      );

      await apiClient.postStream('/api/test', mockFormData);

      const callArgs = (global.fetch as jest.Mock).mock.calls[0];
      expect(callArgs[1].headers).not.toHaveProperty('Content-Type');
    });
  });

  describe('base URL configuration', () => {
    it('uses the base URL from expo constants', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(
        createMockResponse({ ok: true }),
      );

      await apiClient.get('/api/health');

      const url = (global.fetch as jest.Mock).mock.calls[0][0];
      expect(url).toBe('http://localhost:8000/api/health');
    });
  });

  describe('timeout', () => {
    // Simulate an aborted fetch: listen for the AbortSignal and reject
    // with a DOMException-like AbortError when it fires.
    function mockAbortableFetch(latencyMs: number, response?: Response) {
      (global.fetch as jest.Mock).mockImplementation(
        (_url: string, init: RequestInit) =>
          new Promise((resolve, reject) => {
            const signal = init.signal;
            const timer = setTimeout(() => {
              if (response) resolve(response);
              else resolve(createMockResponse({ ok: true }));
            }, latencyMs);
            if (signal) {
              signal.addEventListener('abort', () => {
                clearTimeout(timer);
                const err = new Error('The operation was aborted.');
                err.name = 'AbortError';
                reject(err);
              });
            }
          }),
      );
    }

    beforeEach(() => {
      jest.useFakeTimers();
    });

    afterEach(() => {
      jest.useRealTimers();
    });

    it('passes an AbortSignal to fetch so the request can be cancelled', async () => {
      mockAbortableFetch(100, createMockResponse({ ok: true }));

      const p = apiClient.get('/api/test');
      await jest.advanceTimersByTimeAsync(100);
      await p;

      const init = (global.fetch as jest.Mock).mock.calls[0][1];
      expect(init.signal).toBeInstanceOf(AbortSignal);
    });

    it('returns a TIMEOUT_ERROR envelope when GET exceeds the default 15s timeout', async () => {
      mockAbortableFetch(20_000);

      const promise = apiClient.get('/api/slow');
      // Fire the 15s abort timer.
      await jest.advanceTimersByTimeAsync(15_000);
      const result = await promise;

      expect(result).toEqual({
        error: {
          code: 'TIMEOUT_ERROR',
          message: 'Request timed out after 15000ms',
        },
      });
    });

    it('returns a TIMEOUT_ERROR envelope when POST exceeds the default 15s timeout', async () => {
      mockAbortableFetch(20_000);

      const promise = apiClient.post('/api/slow', { foo: 'bar' });
      await jest.advanceTimersByTimeAsync(15_000);
      const result = await promise;

      expect(result).toEqual({
        error: {
          code: 'TIMEOUT_ERROR',
          message: 'Request timed out after 15000ms',
        },
      });
    });

    it('returns a TIMEOUT_ERROR envelope when DELETE exceeds the default 10s timeout', async () => {
      mockAbortableFetch(20_000);

      const promise = apiClient.delete('/api/slow');
      await jest.advanceTimersByTimeAsync(10_000);
      const result = await promise;

      expect(result).toEqual({
        error: {
          code: 'TIMEOUT_ERROR',
          message: 'Request timed out after 10000ms',
        },
      });
    });

    it('honours a per-call timeoutMs override', async () => {
      mockAbortableFetch(20_000);

      const promise = apiClient.get('/api/slow', { timeoutMs: 500 });
      await jest.advanceTimersByTimeAsync(500);
      const result = await promise;

      expect(result).toEqual({
        error: {
          code: 'TIMEOUT_ERROR',
          message: 'Request timed out after 500ms',
        },
      });
    });

    it('does not abort when the response arrives before the timeout', async () => {
      const mockData = { id: 'ok' };
      mockAbortableFetch(100, createMockResponse(mockData));

      const promise = apiClient.get('/api/fast');
      await jest.advanceTimersByTimeAsync(100);
      const result = await promise;

      expect(result).toEqual({ data: mockData });
    });

    it('disables the timeout entirely when timeoutMs is 0', async () => {
      const mockData = { id: 'eventually' };
      mockAbortableFetch(30_000, createMockResponse(mockData));

      const promise = apiClient.get('/api/eventually', { timeoutMs: 0 });
      // Advance well past any default timeout; the request must still
      // be allowed to complete.
      await jest.advanceTimersByTimeAsync(30_000);
      const result = await promise;

      expect(result).toEqual({ data: mockData });
    });

    it('postStream does not apply a timeout (SSE is long-lived)', async () => {
      // postStream calls fetch directly without fetchWithTimeout, so no
      // AbortSignal is attached. We just assert fetch was called without
      // a signal to lock in this contract.
      (global.fetch as jest.Mock).mockResolvedValue(createMockResponse(null));
      const formData = new FormData();

      await apiClient.postStream('/api/stream', formData);

      const init = (global.fetch as jest.Mock).mock.calls[0][1];
      expect(init.signal).toBeUndefined();
    });

    it('re-throws non-abort errors so callers can distinguish them', async () => {
      (global.fetch as jest.Mock).mockRejectedValue(new Error('boom'));

      await expect(apiClient.get('/api/broken')).rejects.toThrow('boom');
    });
  });
});
