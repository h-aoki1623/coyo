export type TopicKey = 'sports' | 'business' | 'technology' | 'politics' | 'entertainment';

export type RootStackParamList = {
  Home: undefined;
  Talk: { topic: TopicKey; conversationId?: string };
  Feedback: { conversationId: string };
  HistoryList: undefined;
  HistoryDetail: { conversationId: string };
};
