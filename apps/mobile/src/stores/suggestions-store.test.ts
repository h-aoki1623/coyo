import { useSuggestionsStore } from './suggestions-store';
import type { TopicSuggestionsResponse } from '@/types/suggestion';

const mockGet = jest.fn();
jest.mock('@/api/client', () => ({
  apiClient: {
    get: (...args: unknown[]) => mockGet(...args),
  },
}));

const sampleResponse: TopicSuggestionsResponse = {
  personal: [
    {
      id: 'p1',
      title: 'Personal topic',
      summary: 'summary',
      sourceKeyword: 'kw',
      pool: 'personal',
      rank: 1,
    },
  ],
  trending: [
    {
      id: 't1',
      title: 'Trending topic',
      summary: 'summary',
      sourceKeyword: 'kw',
      pool: 'common',
      rank: 1,
    },
  ],
};

describe('useSuggestionsStore', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useSuggestionsStore.getState().reset();
  });

  describe('initial state', () => {
    it('starts empty and not ready', () => {
      const state = useSuggestionsStore.getState();
      expect(state.suggestions).toEqual({ personal: [], trending: [] });
      expect(state.isReady).toBe(false);
      expect(state.isLoading).toBe(false);
    });
  });

  describe('prefetch', () => {
    it('fetches suggestions and stores them', async () => {
      mockGet.mockResolvedValue({ data: sampleResponse });

      await useSuggestionsStore.getState().prefetch();

      expect(mockGet).toHaveBeenCalledWith('/api/topics/suggestions');
      const state = useSuggestionsStore.getState();
      expect(state.suggestions).toEqual(sampleResponse);
      expect(state.isReady).toBe(true);
      expect(state.isLoading).toBe(false);
    });

    it('marks as ready even when fetch fails', async () => {
      mockGet.mockRejectedValue(new Error('network'));

      await useSuggestionsStore.getState().prefetch();

      const state = useSuggestionsStore.getState();
      expect(state.suggestions).toEqual({ personal: [], trending: [] });
      expect(state.isReady).toBe(true);
      expect(state.isLoading).toBe(false);
    });

    it('marks as ready when API returns an error envelope (no data)', async () => {
      mockGet.mockResolvedValue({
        error: { code: 'INTERNAL_ERROR', message: 'oops' },
      });

      await useSuggestionsStore.getState().prefetch();

      const state = useSuggestionsStore.getState();
      expect(state.suggestions).toEqual({ personal: [], trending: [] });
      expect(state.isReady).toBe(true);
    });

    it('reuses an in-flight request instead of firing twice', async () => {
      let resolveFn: (v: { data: TopicSuggestionsResponse }) => void = () => {};
      mockGet.mockReturnValue(
        new Promise((resolve) => {
          resolveFn = resolve;
        }),
      );

      const a = useSuggestionsStore.getState().prefetch();
      const b = useSuggestionsStore.getState().prefetch();
      expect(mockGet).toHaveBeenCalledTimes(1);

      resolveFn({ data: sampleResponse });
      await Promise.all([a, b]);

      expect(useSuggestionsStore.getState().isReady).toBe(true);
    });
  });

  describe('reset', () => {
    it('clears suggestions and ready flag', async () => {
      mockGet.mockResolvedValue({ data: sampleResponse });
      await useSuggestionsStore.getState().prefetch();

      useSuggestionsStore.getState().reset();

      const state = useSuggestionsStore.getState();
      expect(state.suggestions).toEqual({ personal: [], trending: [] });
      expect(state.isReady).toBe(false);
      expect(state.isLoading).toBe(false);
    });

    it('discards an in-flight response that resolves after reset (no cross-user leakage)', async () => {
      let resolveFn: (v: { data: TopicSuggestionsResponse }) => void = () => {};
      mockGet.mockReturnValue(
        new Promise((resolve) => {
          resolveFn = resolve;
        }),
      );

      // User A: kick off a prefetch...
      const promise = useSuggestionsStore.getState().prefetch();

      // ...then sign out before the response arrives.
      useSuggestionsStore.getState().reset();

      // Late response from user A's session resolves now.
      resolveFn({ data: sampleResponse });
      await promise;

      // The store must remain empty — A's data must not land after reset.
      const state = useSuggestionsStore.getState();
      expect(state.suggestions).toEqual({ personal: [], trending: [] });
      expect(state.isReady).toBe(false);
      expect(state.isLoading).toBe(false);
    });
  });
});
