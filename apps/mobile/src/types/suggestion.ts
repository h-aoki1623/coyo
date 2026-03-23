export interface TopicSuggestion {
  id: string;
  title: string;
  summary: string;
  sourceKeyword: string;
  pool: 'common' | 'personal';
  rank: number;
}

export interface TopicSuggestionsResponse {
  personal: TopicSuggestion[];
  trending: TopicSuggestion[];
}
