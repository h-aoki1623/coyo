import { apiClient } from './client';

// Mock the device-id service
jest.mock('@/services/device-id', () => ({
  getOrCreateDeviceId: jest.fn(() => Promise.resolve('test-device-id')),
}));

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
        {
          headers: {
            'Content-Type': 'application/json',
            'X-Device-Id': 'test-device-id',
          },
        },
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

    it('includes the X-Device-Id header', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(
        createMockResponse({ ok: true }),
      );

      await apiClient.get('/api/test');

      const callArgs = (global.fetch as jest.Mock).mock.calls[0];
      expect(callArgs[1].headers['X-Device-Id']).toBe('test-device-id');
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
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Device-Id': 'test-device-id',
          },
          body: JSON.stringify(requestBody),
        },
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
        {
          method: 'DELETE',
          headers: {
            'Content-Type': 'application/json',
            'X-Device-Id': 'test-device-id',
          },
        },
      );
    });

    it('does not return data', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(
        createMockResponse(null),
      );

      const result = await apiClient.delete('/api/test/1');

      expect(result).toBeUndefined();
    });
  });

  describe('postStream', () => {
    it('sends a POST request with FormData and device ID header', async () => {
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
          headers: { 'X-Device-Id': 'test-device-id' },
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
});
