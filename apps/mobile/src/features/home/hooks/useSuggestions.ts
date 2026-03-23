import { useState, useEffect, useCallback } from 'react';

import { apiClient } from '@/api/client';
import type { TopicSuggestionsResponse } from '@/types/suggestion';

const EMPTY_RESPONSE: TopicSuggestionsResponse = { personal: [], trending: [] };

export function useSuggestions() {
  const [suggestions, setSuggestions] = useState<TopicSuggestionsResponse>(EMPTY_RESPONSE);
  const [isLoading, setIsLoading] = useState(true);

  const fetchSuggestions = useCallback(async () => {
    try {
      const result = await apiClient.get<TopicSuggestionsResponse>('/api/topics/suggestions');
      if (result.data) {
        setSuggestions(result.data);
      }
    } catch {
      // Silently fail — suggestions are optional enhancement
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSuggestions();
  }, [fetchSuggestions]);

  return { suggestions, isLoading };
}
