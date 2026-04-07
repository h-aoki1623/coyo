/**
 * Topic suggestions store.
 *
 * Holds the result of GET /api/topics/suggestions so it can be prefetched
 * during auth initialization (before HomeScreen mounts) and read from cache
 * once the user lands on Home. This eliminates the visible delay where the
 * Home screen renders before the suggestions API has resolved.
 */

import { create } from 'zustand';

import { apiClient } from '@/api/client';
import type { TopicSuggestionsResponse } from '@/types/suggestion';

const EMPTY_RESPONSE: TopicSuggestionsResponse = { personal: [], trending: [] };

interface SuggestionsState {
  suggestions: TopicSuggestionsResponse;
  /** True once the first prefetch (success or failure) has settled. */
  isReady: boolean;
  /** True while a fetch is in flight. */
  isLoading: boolean;

  /**
   * Start (or reuse) a fetch of /api/topics/suggestions. Returns a promise
   * that resolves once the fetch settles. Safe to call multiple times — the
   * in-flight promise is shared.
   */
  prefetch: () => Promise<void>;
  /** Clear cached suggestions (e.g., on sign out). */
  reset: () => void;
}

// Module-level coordination across calls. `generation` lets `reset()` cancel
// any in-flight prefetch by invalidating its captured token, so a late
// response from a signed-out session can never land in a fresh store.
let inflight: Promise<void> | null = null;
let generation = 0;

export const useSuggestionsStore = create<SuggestionsState>((set) => ({
  suggestions: EMPTY_RESPONSE,
  isReady: false,
  isLoading: false,

  prefetch: () => {
    if (inflight) return inflight;

    const myGeneration = generation;
    set({ isLoading: true });

    inflight = (async () => {
      try {
        const result = await apiClient.get<TopicSuggestionsResponse>(
          '/api/topics/suggestions',
        );
        // If reset() ran while we were awaiting, drop this response on the
        // floor — the user we fetched it for is no longer the active user.
        if (myGeneration !== generation) return;
        if (result.data) {
          set({ suggestions: result.data });
        }
        // HTTP error envelopes (result.error) are intentionally ignored:
        // suggestions are an optional enhancement and Home falls back to
        // its fixed topic cards. We do not surface them to the user here.
      } catch {
        // Network / parse error — same fallback as the error envelope path.
      } finally {
        if (myGeneration === generation) {
          set({ isReady: true, isLoading: false });
        }
        inflight = null;
      }
    })();
    return inflight;
  },

  reset: () => {
    // Bump the generation so any in-flight prefetch becomes a no-op when
    // it eventually resolves — preventing cross-user cache leakage.
    generation += 1;
    inflight = null;
    set({ suggestions: EMPTY_RESPONSE, isReady: false, isLoading: false });
  },
}));
