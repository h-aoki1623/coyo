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
    // Use mockReset (not clearAllMocks) so queued mockResolvedValueOnce /
    // mockRejectedValueOnce implementations from a prior test that timed
    // out cannot leak into the next test.
    mockGet.mockReset();
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

  it('retries when HomeScreen mounts after a failed first-launch prefetch', async () => {
    // Simulate the production bug: on cold start, the prefetch kicked off
    // from auth-store fails (e.g., Firebase token not yet warm, or
    // /api/auth/session hasn't created the backend user row yet, so
    // /api/topics/suggestions 401s).
    mockGet.mockRejectedValueOnce(new Error('401 Unauthorized'));
    await useSuggestionsStore.getState().prefetch();

    // Sanity check: the failed prefetch left the store empty.
    expect(useSuggestionsStore.getState().suggestions).toEqual({
      personal: [],
      trending: [],
    });

    // Now the HomeScreen mounts. The hook MUST trigger a retry and populate
    // the store — not sit on the empty state forever because `isReady`
    // flipped to true on the failed attempt.
    mockGet.mockResolvedValueOnce({ data: mockResponse });

    const { result } = renderHook(() => useSuggestions());

    await waitFor(() => {
      expect(result.current.suggestions).toEqual(mockResponse);
    });
    expect(mockGet).toHaveBeenCalledTimes(2);
  });

  it('retries when HomeScreen mounts DURING an inflight prefetch that later fails', async () => {
    // Production regression: on a slow cold-start, App.tsx's splash gate
    // releases (either because SPLASH_PREFETCH_TIMEOUT_MS fires or
    // because `isReady` flipped to true) while auth-store's prefetch is
    // still in flight. HomeScreen mounts, the hook sees isLoading=true
    // and skips the retry. The inflight prefetch then resolves as a
    // failure (empty/401/etc.). The hook MUST detect the transition
    // from loading→failed and retry exactly once — it must NOT sit on
    // the empty state until the user kills and relaunches the app.
    let failFirstPrefetch: (err: Error) => void = () => {};
    mockGet.mockImplementationOnce(
      () =>
        new Promise((_, reject) => {
          failFirstPrefetch = reject;
        }),
    );

    // Kick off the initial prefetch (mirrors auth-store.initialize).
    // Do NOT await — the test point is that HomeScreen mounts WHILE
    // the request is still in flight.
    const initialPrefetch = useSuggestionsStore.getState().prefetch();
    expect(useSuggestionsStore.getState().isLoading).toBe(true);

    // HomeScreen mounts with isLoading=true. The hook must not retry
    // yet, but it must arm itself to retry once the inflight settles.
    const { result } = renderHook(() => useSuggestions());
    expect(mockGet).toHaveBeenCalledTimes(1);

    // Now the inflight prefetch fails. The next call should succeed.
    mockGet.mockResolvedValueOnce({ data: mockResponse });
    failFirstPrefetch(new Error('401 Unauthorized'));
    await initialPrefetch;

    // The hook must observe isLoading→false while hasLoaded is still
    // false, and trigger exactly one retry.
    await waitFor(() => {
      expect(result.current.suggestions).toEqual(mockResponse);
    });
    expect(mockGet).toHaveBeenCalledTimes(2);
  });

  it('does not retry more than once per mount when the retry itself fails', async () => {
    // Bound the retry: even if the retry fails too, the hook must
    // stop — a persistently failing backend must not be hammered on
    // every state transition.
    mockGet.mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => useSuggestions());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Give the effect plenty of time to (incorrectly) fire another retry.
    await new Promise((r) => setTimeout(r, 50));

    // Exactly one call from the hook's mount-time fetch. No retry storm.
    expect(mockGet).toHaveBeenCalledTimes(1);
    expect(result.current.suggestions).toEqual({ personal: [], trending: [] });
  });
});
