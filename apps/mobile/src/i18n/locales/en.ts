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
    waitingForCoto: 'Waiting for Coto...',
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
    messageFrom: 'Message from Coto',
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
      'Coto needs access to your microphone for conversation practice. Please enable it in Settings.',
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
