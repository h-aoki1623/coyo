import { useEffect, useRef } from 'react';

import { useSuggestionsStore } from '@/stores/suggestions-store';

/**
 * Reads cached topic suggestions from the store. The store is normally
 * primed by `auth-store.initialize()` immediately after sign-in, so by
 * the time HomeScreen mounts the data is already available.
 *
 * If the cache is empty because the prefetch hasn't run yet (hot reload)
 * or because it failed (cold-start auth race, stale Firebase token, etc.),
 * this hook triggers a retry — at most once per hook instance, to bound
 * network traffic against a persistently failing backend.
 *
 * The effect depends on both `hasLoaded` and `isLoading` so that it can
 * react to the transition `isLoading=true → false` that happens when the
 * initial auth-store prefetch settles AFTER HomeScreen has already
 * mounted. The previous (empty-deps) implementation had a latent bug:
 * when App.tsx's splash gate released while the initial prefetch was
 * still in flight (either because `isReady` had flipped or because
 * `SPLASH_PREFETCH_TIMEOUT_MS` fired), HomeScreen would mount with
 * `isLoading=true`, the effect would skip, and the effect would never
 * run again — locking the user into an empty Home until a full app
 * restart. This was the original "suggestions don't show on first
 * launch" production bug.
 */
export function useSuggestions() {
  const suggestions = useSuggestionsStore((s) => s.suggestions);
  const hasLoaded = useSuggestionsStore((s) => s.hasLoaded);
  const isLoading = useSuggestionsStore((s) => s.isLoading);

  // Guard against retry storms: a persistently failing backend would
  // otherwise re-trigger the effect on every `isLoading` transition.
  const didRetryRef = useRef(false);

  useEffect(() => {
    if (didRetryRef.current) return;
    if (hasLoaded) return;
    if (isLoading) return;
    didRetryRef.current = true;
    useSuggestionsStore.getState().prefetch();
  }, [hasLoaded, isLoading]);

  return { suggestions, isLoading: isLoading && !hasLoaded };
}
