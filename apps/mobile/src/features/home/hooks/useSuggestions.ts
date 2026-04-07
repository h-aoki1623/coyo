import { useEffect } from 'react';

import { useSuggestionsStore } from '@/stores/suggestions-store';

/**
 * Reads cached topic suggestions from the store. The store is normally
 * primed by `auth-store.initialize()` immediately after sign-in, so by the
 * time HomeScreen mounts the data is already available. If for any reason
 * the cache is empty (e.g., a hot reload), this hook triggers a fetch.
 */
export function useSuggestions() {
  const suggestions = useSuggestionsStore((s) => s.suggestions);
  const isReady = useSuggestionsStore((s) => s.isReady);
  const isLoading = useSuggestionsStore((s) => s.isLoading);

  useEffect(() => {
    if (!isReady && !isLoading) {
      useSuggestionsStore.getState().prefetch();
    }
  }, [isReady, isLoading]);

  return { suggestions, isLoading: isLoading && !isReady };
}
