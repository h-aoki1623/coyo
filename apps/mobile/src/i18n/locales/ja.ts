/**
 * Japanese translations.
 * This is the primary language for the app (Japan market).
 */
const ja = {
  // Home Screen
  home: {
    greeting: 'こんにちは',
    subtitle: '今日は何について話す？',
    topics: 'TOPICS',
    pausedBanner: {
      title: '中断中のトーク',
      hint: 'タップして再開',
      resume: '再開',
    },
  },

  // Topics
  topics: {
    sports: 'スポーツ',
    business: 'ビジネス',
    politics: '政治',
    technology: 'テクノロジー',
    entertainment: 'エンタメ',
  },

  // Talk Screen
  talk: {
    endButton: '終了する',
    emptyTitle: '英会話をはじめよう！',
    emptySubtitle: '下のマイクボタンをタップして、{{topic}}について話しましょう。',
    recordHint: '録音ボタンを押して話す',
    speakNow: '話してください...',
    processing: '処理中...',
    processingVoice: '音声を処理中...',
    waitingForCoyo: 'Coyo が考え中...',
    completionText: 'トーク終了 · {{duration}}',
    viewFeedback: 'フィードバックを見る',
    lessThanMinute: '1分未満',
    minutesDuration: '{{mins}}分間',
  },

  // Talk - Corrections
  corrections: {
    checking: '確認中...',
    noCorrections: '訂正なし',
    correctionCount: '{{count}}件の訂正',
    correctionCountOne: '1件の訂正',
  },

  // Talk - End Conversation Dialog
  endDialog: {
    title: '会話を終了',
    message: '会話を終了してフィードバックを確認しますか？',
    cancel: 'キャンセル',
    end: '終了',
  },

  // Feedback Screen
  feedback: {
    title: 'フィードバック',
    statExchanges: 'やりとり',
    statCorrections: '添削',
    statClean: '訂正なし',
    loading: 'フィードバックを読み込み中...',
    errorTitle: 'フィードバックを読み込めませんでした',
    retry: '再試行',
    goHome: 'ホームに戻る',
  },

  // Empty Feedback (Perfect English)
  emptyFeedback: {
    title: '完璧な英語でした！',
    messageFrom: 'Coyo からのメッセージ',
    body: 'あなたの英語はネイティブも納得のレベルです。次のトークも楽しみにしています！',
  },

  // History List Screen
  history: {
    title: 'トーク履歴',
    emptyTitle: 'まだ履歴がありません',
    emptySubtitle: '会話するたびに、ここに\nトーク履歴が残ります。',
    emptyHint:
      'トークが終わると自動的にここへ保存されます。英語の添削ポイントもあとからいつでも確認できます。',
    deleteTitle: 'トーク履歴を削除',
    deleteMessage: 'トーク履歴を削除しますか？この操作は取り消せません。',
    deleteCancel: 'キャンセル',
    deleteConfirm: '削除',
  },

  // History Detail Screen
  historyDetail: {
    title: 'トーク履歴',
    tabFeedback: 'フィードバック',
    tabChatHistory: 'チャット履歴',
    chatEndLabel: 'トーク終了 · {{duration}}',
    emptyChatHistory: 'この会話にメッセージはありません。',
    errorLoadDetail: '詳細を読み込めませんでした',
  },

  // History - Date Sections
  dates: {
    today: '今日',
    yesterday: '昨日',
    dateFormat: '{{month}}月{{day}}日',
  },

  // History - Duration Formats
  duration: {
    none: '--',
    lessThanMinute: '1分未満',
    minutes: '{{mins}}分間',
  },

  // Offline Screen
  offline: {
    title: 'オフラインです',
    body: 'このアプリを使用するにはインターネット接続が必要です。接続を確認してからもう一度お試しください。',
    retry: '再試行',
  },

  // Error Messages
  errors: {
    connectionTitle: '接続エラー',
    connectionMessage: 'サーバーに接続できませんでした。ネットワークを確認してもう一度お試しください。',
    genericError: 'エラー',
    resumeError: '会話を再開できませんでした。もう一度お試しください。',
    loadHistoryError: 'トーク履歴を読み込めませんでした。',
    loadDetailError: '会話の詳細を読み込めませんでした。',
    deleteError: '会話を削除できませんでした。',
    endConversationError: '会話を終了できませんでした。もう一度お試しください。',
    recordingError: '録音を開始できませんでした。もう一度お試しください。',
    micPermissionTitle: 'マイクの許可が必要です',
    micPermissionMessage:
      'Coyo で英会話を練習するにはマイクへのアクセスが必要です。設定から許可してください。',
  },

  // Common
  common: {
    error: 'エラー',
    retry: '再試行',
    cancel: 'キャンセル',
    goBack: '戻る',
  },
} as const;

export default ja;
