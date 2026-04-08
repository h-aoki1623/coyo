import { useEffect } from 'react';

import { useSuggestionsStore } from '@/stores/suggestions-store';

/**
 * Reads cached topic suggestions from the store. The store is normally
 * primed by `auth-store.initialize()` immediately after sign-in, so by the
 * time HomeScreen mounts the data is already available.
 *
 * If the cache is empty because the prefetch hasn't run yet (hot reload) or
 * because it ran but failed (cold-start auth race where the Firebase token
 * or backend user row wasn't ready), this hook triggers a single retry on
 * mount. We gate on `hasLoaded` rather than `isReady` so a failed first
 * attempt does not lock the user into an empty Home until a full app
 * restart. The retry fires at most once per hook instance so a persistently
 * failing API can't hammer the backend — a subsequent retry requires the
 * user to remount the screen (navigate away and back).
 */
export function useSuggestions() {
  const suggestions = useSuggestionsStore((s) => s.suggestions);
  const hasLoaded = useSuggestionsStore((s) => s.hasLoaded);
  const isLoading = useSuggestionsStore((s) => s.isLoading);

  useEffect(() => {
    // Read the store directly (not the subscribed values) so this effect
    // runs exactly once per mount regardless of state changes while we wait.
    // The empty dep array is intentional: re-running on state changes would
    // create an infinite retry loop against a persistently failing backend.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    const state = useSuggestionsStore.getState();
    if (!state.hasLoaded && !state.isLoading) {
      state.prefetch();
    }
  }, []);

  return { suggestions, isLoading: isLoading && !hasLoaded };
}
