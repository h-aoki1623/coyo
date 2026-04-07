import { renderHook, waitFor } from '@testing-library/react-native';

import { useSuggestions } from '../useSuggestions';
import { useSuggestionsStore } from '@/stores/suggestions-store';
import type { TopicSuggestionsResponse } from '@/types/suggestion';

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
      pool: 'personal',
      rank: 1,
    },
  ],
  trending: [
    {
      id: 't1',
      title: 'Breaking Tech News',
      summary: 'AI developments this week',
      sourceKeyword: 'technology',
      pool: 'common',
      rank: 1,
    },
  ],
};

describe('useSuggestions', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useSuggestionsStore.getState().reset();
  });

  it('returns cached suggestions immediately when the store is already primed', async () => {
    mockGet.mockResolvedValue({ data: mockResponse });
    await useSuggestionsStore.getState().prefetch();
    mockGet.mockClear();

    const { result } = renderHook(() => useSuggestions());

    expect(result.current.isLoading).toBe(false);
    expect(result.current.suggestions).toEqual(mockResponse);
    // No additional API call — the store cache is reused.
    expect(mockGet).not.toHaveBeenCalled();
  });

  it('triggers a prefetch when the store is empty', async () => {
    mockGet.mockResolvedValue({ data: mockResponse });

    const { result } = renderHook(() => useSuggestions());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.suggestions).toEqual(mockResponse);
    expect(mockGet).toHaveBeenCalledWith('/api/topics/suggestions');
  });

  it('handles API failure gracefully and exposes empty suggestions', async () => {
    mockGet.mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => useSuggestions());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.suggestions).toEqual({ personal: [], trending: [] });
  });

  it('does not refetch when called multiple times concurrently', async () => {
    mockGet.mockResolvedValue({ data: mockResponse });

    renderHook(() => useSuggestions());
    renderHook(() => useSuggestions());

    await waitFor(() => {
      expect(useSuggestionsStore.getState().isReady).toBe(true);
    });

    expect(mockGet).toHaveBeenCalledTimes(1);
  });
});
