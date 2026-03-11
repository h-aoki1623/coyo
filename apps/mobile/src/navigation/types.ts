export type TopicKey = 'sports' | 'business' | 'technology' | 'politics' | 'entertainment';

export type AuthStackParamList = {
  Welcome: undefined;
  AuthMethod: { mode: 'signUp' | 'signIn' };
  SignUpForm: undefined;
  SignInForm: undefined;
  EmailVerification: { email: string };
};

export type RootStackParamList = {
  Home: undefined;
  Talk: { topic: TopicKey; conversationId?: string };
  Feedback: { conversationId: string };
  HistoryList: undefined;
  HistoryDetail: { conversationId: string };
};
