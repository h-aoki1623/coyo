import { renderHook, waitFor } from '@testing-library/react-native';

import { useSuggestions } from '../useSuggestions';
import type { TopicSuggestionsResponse } from '@/types/suggestion';

// Mock apiClient
const mockGet = jest.fn();
jest.mock('@/api/client', () => ({
  apiClient: {
    get: (...args: unknown[]) => mockGet(...args),
  },
}));

const mockResponse: TopicSuggestionsResponse = {
  personal: [
    {
      id: 'p1',
      title: 'Your Basketball Update',
      summary: 'Latest news from your favorite teams',
      sourceKeyword: 'basketball',
      pool: 'personal' as const,
      rank: 1,
    },
  ],
  trending: [
    {
      id: 't1',
      title: 'Breaking Tech News',
      summary: 'AI developments this week',
      sourceKeyword: 'technology',
      pool: 'common' as const,
      rank: 1,
    },
  ],
};

describe('useSuggestions', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('returns empty suggestions and loading true initially', () => {
    mockGet.mockReturnValue(new Promise(() => {})); // Never resolves

    const { result } = renderHook(() => useSuggestions());

    expect(result.current.isLoading).toBe(true);
    expect(result.current.suggestions).toEqual({
      personal: [],
      trending: [],
    });
  });

  it('fetches and returns suggestions from API', async () => {
    mockGet.mockResolvedValue({ data: mockResponse });

    const { result } = renderHook(() => useSuggestions());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.suggestions).toEqual(mockResponse);
    expect(mockGet).toHaveBeenCalledWith('/api/topics/suggestions');
  });

  it('handles API error gracefully and returns empty suggestions', async () => {
    mockGet.mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => useSuggestions());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.suggestions).toEqual({
      personal: [],
      trending: [],
    });
  });

  it('handles API returning error envelope (no data) gracefully', async () => {
    mockGet.mockResolvedValue({
      error: { code: 'INTERNAL_ERROR', message: 'Server error' },
    });

    const { result } = renderHook(() => useSuggestions());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // data is undefined, so suggestions stay as the empty default
    expect(result.current.suggestions).toEqual({
      personal: [],
      trending: [],
    });
  });

  it('sets isLoading to false after successful fetch', async () => {
    mockGet.mockResolvedValue({ data: mockResponse });

    const { result } = renderHook(() => useSuggestions());

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
  });

  it('sets isLoading to false after failed fetch', async () => {
    mockGet.mockRejectedValue(new Error('timeout'));

    const { result } = renderHook(() => useSuggestions());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
  });

  it('calls the correct API endpoint', async () => {
    mockGet.mockResolvedValue({ data: mockResponse });

    renderHook(() => useSuggestions());

    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledTimes(1);
    });

    expect(mockGet).toHaveBeenCalledWith('/api/topics/suggestions');
  });
});
