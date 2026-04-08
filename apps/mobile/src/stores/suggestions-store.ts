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
  /**
   * True once the first prefetch attempt (success OR failure) has settled.
   * Used by the splash gate to decide when to hide the native splash — it
   * intentionally does NOT distinguish success from failure so a failing
   * API never strands the user on the splash screen.
   */
  isReady: boolean;
  /**
   * True once a prefetch has successfully populated `suggestions`. Used by
   * `useSuggestions` to decide whether to retry on HomeScreen mount. Without
   * this, a failed first-launch prefetch (e.g., cold-start race where the
   * Firebase token or backend user row isn't ready yet) would flip
   * `isReady=true` and the hook would never retry, leaving the user with an
   * empty Home until a full app restart.
   */
  hasLoaded: boolean;
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
  hasLoaded: false,
  isLoading: false,

  prefetch: () => {
    if (inflight) return inflight;

    const myGeneration = generation;
    set({ isLoading: true });

    inflight = (async () => {
      let succeeded = false;
      try {
        const result = await apiClient.get<TopicSuggestionsResponse>(
          '/api/topics/suggestions',
        );
        // If reset() ran while we were awaiting, drop this response on the
        // floor — the user we fetched it for is no longer the active user.
        if (myGeneration !== generation) return;
        if (result.data) {
          set({ suggestions: result.data });
          succeeded = true;
        }
        // HTTP error envelopes (result.error) are intentionally not surfaced:
        // suggestions are an optional enhancement and Home falls back to its
        // fixed topic cards. But we DO track success separately via
        // `hasLoaded` so that `useSuggestions` can retry on HomeScreen mount
        // after a transient failure (e.g., the cold-start auth race).
      } catch {
        // Network / parse error — same handling as the error envelope path.
      } finally {
        if (myGeneration === generation) {
          set((state) => ({
            isReady: true,
            isLoading: false,
            // Only flip hasLoaded to true on a successful fetch. Once true,
            // leave it true — a later failing refetch must not invalidate
            // previously cached data.
            hasLoaded: succeeded || state.hasLoaded,
          }));
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
    set({
      suggestions: EMPTY_RESPONSE,
      isReady: false,
      hasLoaded: false,
      isLoading: false,
    });
  },
}));
