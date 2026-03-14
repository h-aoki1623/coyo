/**
 * English translations.
 * Fallback language for non-Japanese OS locales.
 */
const en = {
  // Home Screen
  home: {
    greeting: 'Hello',
    subtitle: 'What do you want to talk about today?',
    topics: 'TOPICS',
    pausedBanner: {
      title: 'Paused Conversation',
      hint: 'Tap to resume',
      resume: 'Resume',
    },
    signOut: 'Sign Out',
  },

  // Topics
  topics: {
    sports: 'Sports',
    business: 'Business',
    politics: 'Politics',
    technology: 'Technology',
    entertainment: 'Entertainment',
  },

  // Talk Screen
  talk: {
    endButton: 'End',
    emptyTitle: 'Ready to Practice!',
    emptySubtitle: 'Tap the microphone button below and start speaking about {{topic}}.',
    recordHint: 'Press Record to start speaking',
    speakNow: 'Speak now...',
    processing: 'Processing...',
    processingVoice: 'Processing your voice...',
    waitingForCoyo: 'Waiting for Coyo...',
    completionText: 'Talk ended \u00B7 {{duration}}',
    viewFeedback: 'View Feedback',
    lessThanMinute: 'Less than 1 min',
    minutesDuration: '{{mins}} min',
  },

  // Talk - Corrections
  corrections: {
    checking: 'Checking...',
    noCorrections: 'No corrections',
    correctionCount: '{{count}} corrections',
    correctionCountOne: '1 correction',
  },

  // Talk - End Conversation Dialog
  endDialog: {
    title: 'End Conversation',
    message: 'Would you like to end this conversation and see your feedback?',
    cancel: 'Cancel',
    end: 'End',
  },

  // Feedback Screen
  feedback: {
    title: 'Feedback',
    statExchanges: 'Exchanges',
    statCorrections: 'Corrections',
    statClean: 'Clean',
    loading: 'Loading feedback...',
    errorTitle: 'Could not load feedback',
    retry: 'Try Again',
    goHome: 'Back to Home',
  },

  // Empty Feedback (Perfect English)
  emptyFeedback: {
    title: 'Your English was perfect!',
    messageFrom: 'Message from Coyo',
    body: "Your English is at a native level. We're looking forward to your next talk!",
  },

  // History List Screen
  history: {
    title: 'Talk History',
    emptyTitle: 'No history yet',
    emptySubtitle: 'Your conversation history\nwill appear here.',
    emptyHint:
      'Conversations are automatically saved here after they end. You can review correction points anytime.',
    deleteTitle: 'Delete Talk History',
    deleteMessage: 'Delete this conversation? This action cannot be undone.',
    deleteCancel: 'Cancel',
    deleteConfirm: 'Delete',
  },

  // History Detail Screen
  historyDetail: {
    title: 'Talk History',
    tabFeedback: 'Feedback',
    tabChatHistory: 'History',
    chatEndLabel: 'Talk ended \u00B7 {{duration}}',
    emptyChatHistory: 'No messages in this conversation.',
    errorLoadDetail: 'Could not load details',
  },

  // History - Date Sections
  dates: {
    today: 'Today',
    yesterday: 'Yesterday',
    dateFormat: '{{month}}/{{day}}',
  },

  // History - Duration Formats
  duration: {
    none: '--',
    lessThanMinute: '< 1 min',
    minutes: '{{mins}} min',
  },

  // Offline Screen
  offline: {
    title: "You're Offline",
    body: 'This app requires an internet connection. Please check your connection and try again.',
    retry: 'Retry',
  },

  // Error Messages
  errors: {
    connectionTitle: 'Connection Error',
    connectionMessage:
      'Could not connect to the server. Please check your network and try again.',
    genericError: 'Error',
    resumeError: 'Could not resume the conversation. Please try again.',
    loadHistoryError: 'Could not load conversation history.',
    loadDetailError: 'Could not load conversation details.',
    deleteError: 'Could not delete the conversation.',
    endConversationError: 'Failed to end conversation. Please try again.',
    recordingError: 'Failed to start recording. Please try again.',
    micPermissionTitle: 'Microphone Permission Required',
    micPermissionMessage:
      'Coyo needs access to your microphone for conversation practice. Please enable it in Settings.',
  },

  // Auth Screens
  auth: {
    welcome: {
      signIn: 'Sign In',
      headline: 'Your English improves\nas you speak.',
      subtitle:
        'Enjoy natural English conversation with AI while getting real-time corrections.',
      getStarted: 'Get Started Free',
    },
    modal: {
      createAccount: 'Create Account',
      signIn: 'Sign In',
      continueWithEmail: 'Continue with Email',
      continueWithGoogle: 'Continue with Google',
      continueWithApple: 'Continue with Apple',
      termsPrefix: 'By continuing, you agree to Coyo\'s ',
      termsOfService: 'Terms of Service',
      termsConnector: ' and ',
      privacyPolicy: 'Privacy Policy',
      termsSuffix: '.',
      hasAccountPrompt: 'Already have an account? ',
      noAccountPrompt: "Don't have an account? ",
      signUp: 'Sign Up',
    },
    signUp: {
      title: 'Sign Up',
      name: 'Name',
      email: 'Email',
      password: 'Password',
      submit: 'Create Account',
    },
    signIn: {
      title: 'Sign In',
      email: 'Email',
      password: 'Password',
      submit: 'Sign In',
      forgotPassword: 'Forgot password?',
    },
    verification: {
      title: 'Check Your Email',
      description:
        'We sent you a verification email. Tap the link to activate your account.',
      sentTo: 'Verification sent',
      step1: 'Open your email app',
      step2: 'Find the email from Coyo (check your spam folder too)',
      step3: 'Tap "Verify your email address"',
      notVerified: 'Not verified yet',
      checkFailed: 'Verification check failed. Please try again.',
      confirm: 'I\'ve Verified',
      didNotReceive: "Didn't receive it? ",
      resend: 'Resend',
      resendCooldown: 'Resend ({{seconds}}s)',
    },
    signOut: 'Sign Out',
  },

  // Firebase Auth errors
  firebaseErrors: {
    emailAlreadyInUse: 'This email address is already registered.',
    invalidEmail: 'Please enter a valid email address.',
    weakPassword: 'Password must be at least 8 characters.',
    invalidCredential: 'Incorrect email or password.',
    tooManyRequests: 'Too many attempts. Please try again later.',
    networkError: 'Network error. Please check your connection.',
    userDisabled: 'This account has been disabled.',
    signUpFailed: 'Sign-up failed. Please try again.',
    signInFailed: 'Sign-in failed. Please try again.',
    signOutFailed: 'Sign-out failed. Please try again.',
    resendFailed: 'Failed to resend verification email.',
  },

  // Common
  common: {
    error: 'Error',
    retry: 'Retry',
    cancel: 'Cancel',
    goBack: 'Go back',
  },
} as const;

export default en;
