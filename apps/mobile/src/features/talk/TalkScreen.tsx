import { useCallback, useEffect, useRef, useState } from 'react';
import {
  View,
  FlatList,
  Alert,
  ActivityIndicator,
  Text,
  Pressable,
  StyleSheet,
  type LayoutChangeEvent,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { apiClient } from '@/api/client';
import { Colors } from '@/constants/colors';
import { Typography } from '@/constants/typography';
import { t } from '@/i18n';
import { useConversationStore } from '@/stores/conversation-store';
import { useAudioStore } from '@/stores/audio-store';
import { CoyoAvatar, BackIcon } from '@/components/icons';
import type { RootStackParamList } from '@/navigation/types';
import type { Turn } from '@/types/conversation';
import { MessageBubble, AiTypingBubble, ProcessingBubble } from './components/MessageBubble';
import { RecordButton } from './components/RecordButton';
import { RecordingControls } from './components/RecordingControls';
import { ErrorBanner } from './components/ErrorBanner';
import { useAudioRecording } from './hooks/useAudioRecording';
import { useTurnStreaming } from './hooks/useTurnStreaming';

type Props = NativeStackScreenProps<RootStackParamList, 'Talk'>;

/**
 * Custom header for the Talk screen.
 * Shows CO logo on the left and red "end" button on the right.
 */
function TalkHeader({
  onEnd,
  onBack,
  isEnding,
}: {
  onEnd: () => void;
  onBack: () => void;
  isEnding: boolean;
}) {
  return (
    <View style={styles.header}>
      <View style={styles.headerLeft}>
        <Pressable
          onPress={onBack}
          style={styles.headerBackButton}
          accessibilityRole="button"
          accessibilityLabel={t('common.goBack')}
        >
          <BackIcon size={16} color="#3B82F6" />
        </Pressable>
        <CoyoAvatar size={32} />
        <Text style={styles.headerTitle}>Coyo</Text>
      </View>
      <Pressable
        onPress={onEnd}
        disabled={isEnding}
        style={styles.endButton}
        testID="end-conversation"
        accessibilityRole="button"
        accessibilityLabel={t('talk.endButton')}
      >
        {isEnding ? (
          <ActivityIndicator size="small" color={Colors.buttonDangerText} />
        ) : (
          <Text style={styles.endButtonText}>{t('talk.endButton')}</Text>
        )}
      </Pressable>
    </View>
  );
}

/**
 * Fixed footer bar with "View Feedback" button.
 * Shown at the bottom of the screen when conversation has ended.
 */
function CompletionFooter({ onViewFeedback }: { onViewFeedback: () => void }) {
  return (
    <View style={styles.completionFooter}>
      <Pressable
        style={({ pressed }) => [
          styles.feedbackButton,
          pressed && styles.feedbackButtonPressed,
        ]}
        onPress={onViewFeedback}
        testID="view-feedback"
        accessibilityRole="button"
        accessibilityLabel={t('talk.viewFeedback')}
      >
        <Text style={styles.feedbackButtonText}>{t('talk.viewFeedback')}</Text>
      </Pressable>
    </View>
  );
}

export function TalkScreen({ navigation, route }: Props) {
  const { topic, conversationId } = route.params;
  const flatListRef = useRef<FlatList<Turn>>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [conversationDuration, setConversationDuration] = useState('');
  const conversationStartTime = useRef(Date.now());

  const turns = useConversationStore((s) => s.turns);
  const corrections = useConversationStore((s) => s.corrections);
  const status = useConversationStore((s) => s.status);
  const setStatus = useConversationStore((s) => s.setStatus);
  const recordingStatus = useAudioStore((s) => s.recordingStatus);
  const setRecordingStatus = useAudioStore((s) => s.setRecordingStatus);

  const { startRecording, stopRecording } = useAudioRecording();

  const activeConversationId = conversationId ?? '';
  const { isStreaming, isUserProcessing, isAiThinking, processTurn } = useTurnStreaming(activeConversationId);

  // Hide the default navigation header
  useEffect(() => {
    navigation.setOptions({
      headerShown: false,
    });
  }, [navigation]);

  // Auto-scroll: passively track FlatList dimensions via callbacks,
  // but ONLY trigger scrolls from specific state changes (useEffects/handlers).
  // onContentSizeChange updates the ref but never triggers a scroll,
  // so CorrectionCard open/close won't cause unwanted scrolls.
  const contentHeightRef = useRef(0);
  const layoutHeightRef = useRef(0);

  const scrollToBottom = useCallback(() => {
    const offset = Math.max(0, contentHeightRef.current - layoutHeightRef.current);
    flatListRef.current?.scrollToOffset({ offset, animated: true });
  }, []);

  const handleContentSizeChange = useCallback((_w: number, h: number) => {
    contentHeightRef.current = h;
  }, []);

  const handleListLayout = useCallback((e: LayoutChangeEvent) => {
    layoutHeightRef.current = e.nativeEvent.layout.height;
  }, []);

  // Scroll when new turns are added (user message / AI message)
  useEffect(() => {
    if (turns.length > 0) {
      const timer = setTimeout(scrollToBottom, 200);
      return () => clearTimeout(timer);
    }
  }, [turns.length, scrollToBottom]);

  // Scroll when footer bubbles appear (ProcessingBubble / AiTypingBubble)
  useEffect(() => {
    if (isUserProcessing || isAiThinking) {
      const timer = setTimeout(scrollToBottom, 200);
      return () => clearTimeout(timer);
    }
  }, [isUserProcessing, isAiThinking, scrollToBottom]);

  const formatDuration = useCallback((): string => {
    const elapsed = Math.floor((Date.now() - conversationStartTime.current) / 1000);
    const mins = Math.floor(elapsed / 60);
    if (mins === 0) return t('talk.lessThanMinute');
    return t('talk.minutesDuration', { mins });
  }, []);

  const handleGoBack = useCallback(() => {
    navigation.goBack();
  }, [navigation]);

  const handleEndConversation = useCallback(() => {
    if (!activeConversationId) return;

    Alert.alert(
      t('endDialog.title'),
      t('endDialog.message'),
      [
        { text: t('endDialog.cancel'), style: 'cancel' },
        {
          text: t('endDialog.end'),
          style: 'default',
          onPress: async () => {
            setStatus('ending');
            try {
              await apiClient.post(`/api/conversations/${activeConversationId}/end`);
              setConversationDuration(formatDuration());
              setStatus('completed');
            } catch {
              setStatus('active');
              Alert.alert(t('errors.genericError'), t('errors.endConversationError'));
            }
          },
        },
      ],
    );
  }, [activeConversationId, setStatus, formatDuration]);

  const handleViewFeedback = useCallback(() => {
    navigation.replace('Feedback', { conversationId: activeConversationId });
  }, [navigation, activeConversationId]);

  const handleStartRecording = useCallback(async () => {
    setErrorMessage(null);
    await startRecording();
    setTimeout(scrollToBottom, 200);
  }, [startRecording, scrollToBottom]);

  const handleCancelRecording = useCallback(async () => {
    await stopRecording();
    setRecordingStatus('idle');
  }, [stopRecording, setRecordingStatus]);

  const handleSendRecording = useCallback(async () => {
    const uri = await stopRecording();
    if (uri) {
      await processTurn(uri);
    }
  }, [stopRecording, processTurn]);

  const handleRetryError = useCallback(() => {
    setErrorMessage(null);
  }, []);

  const isEnding = status === 'ending';
  const isCompleted = status === 'completed';
  const isRecording = recordingStatus === 'recording';
  const isProcessing = recordingStatus === 'processing';
  const canRecord = !isStreaming && !isEnding && !isCompleted && !isProcessing;

  const renderTurn = useCallback(
    ({ item }: { item: Turn }) => {
      const correction = corrections[item.id];
      return <MessageBubble turn={item} correction={correction} animate />;
    },
    [corrections],
  );

  const renderFooter = useCallback(() => {
    const elements: React.ReactElement[] = [];

    // User processing bubble (waiting for STT result)
    if (isUserProcessing) {
      elements.push(<ProcessingBubble key="user-processing" />);
    }

    // AI typing indicator (dots) — shown from stt_result until audio playback starts
    if (isAiThinking) {
      elements.push(<AiTypingBubble key="ai-typing" />);
    }

    // Completion label (inside the scrollable thread, above the fixed footer)
    if (isCompleted) {
      elements.push(
        <View key="completion-label" style={styles.completionLabel}>
          <Text style={styles.completionLabelText}>
            {t('talk.completionText', { duration: conversationDuration })}
          </Text>
        </View>,
      );
    }

    if (elements.length === 0) return null;

    return <View>{elements}</View>;
  }, [isUserProcessing, isAiThinking, isCompleted, conversationDuration]);

  // Determine which bottom control to show
  const renderBottomControls = () => {
    if (isCompleted) {
      return <CompletionFooter onViewFeedback={handleViewFeedback} />;
    }

    if (isRecording) {
      return (
        <RecordingControls
          onCancel={handleCancelRecording}
          onSend={handleSendRecording}
        />
      );
    }

    if (isProcessing || isStreaming) {
      return (
        <RecordButton
          onPress={handleStartRecording}
          processing
          processingText={isProcessing ? t('talk.processingVoice') : t('talk.waitingForCoyo')}
        />
      );
    }

    return <RecordButton onPress={handleStartRecording} disabled={!canRecord} />;
  };

  // Get localized topic name for empty state
  const topicLabel = t(`topics.${topic}`);

  return (
    <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
      <TalkHeader onEnd={handleEndConversation} onBack={handleGoBack} isEnding={isEnding} />

      {/* Message area */}
      {turns.length === 0 && !isStreaming ? (
        <View style={styles.emptyState}>
          <CoyoAvatar size={56} />
          <Text style={styles.emptyTitle}>{t('talk.emptyTitle')}</Text>
          <Text style={styles.emptySubtitle}>
            {t('talk.emptySubtitle', { topic: topicLabel })}
          </Text>
        </View>
      ) : (
        <FlatList
          ref={flatListRef}
          data={turns}
          renderItem={renderTurn}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.messageList}
          showsVerticalScrollIndicator={false}
          ListFooterComponent={renderFooter}
          onLayout={handleListLayout}
          onContentSizeChange={handleContentSizeChange}
        />
      )}

      {/* Error banner */}
      {errorMessage ? (
        <ErrorBanner
          message={errorMessage}
          onRetry={handleRetryError}
        />
      ) : null}

      {/* Bottom controls */}
      {renderBottomControls()}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.surfacePrimary,
  },
  // Header
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    height: 56,
    backgroundColor: Colors.surfacePrimary,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  headerBackButton: {
    justifyContent: 'center',
    alignItems: 'center',
    paddingRight: 4,
  },
  headerTitle: {
    ...Typography.bodyLarge.en,
    color: Colors.textPrimary,
  },
  endButton: {
    backgroundColor: Colors.buttonDangerBg,
    borderRadius: 8,
    height: 32,
    paddingHorizontal: 14,
    justifyContent: 'center',
    alignItems: 'center',
  },
  endButtonText: {
    ...Typography.body.ja,
    color: Colors.buttonDangerText,
    includeFontPadding: false,
    textAlignVertical: 'center',
  },
  // Messages
  messageList: {
    paddingTop: 16,
    paddingBottom: 16,
    gap: 16,
  },
  emptyState: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 40,
    gap: 8,
  },
  emptyTitle: {
    ...Typography.title.en,
    color: Colors.textPrimary,
    marginTop: 8,
  },
  emptySubtitle: {
    ...Typography.bodySmall.en,
    color: Colors.textSecondary,
    textAlign: 'center',
  },
  // Completion label (inside scrollable thread)
  completionLabel: {
    paddingTop: 14,
    paddingBottom: 13,
    alignItems: 'center',
  },
  completionLabelText: {
    ...Typography.caption.ja,
    color: Colors.textTertiary,
    textAlign: 'center',
  },
  // Completion footer (fixed bar below thread)
  completionFooter: {
    backgroundColor: Colors.surfacePrimary,
    borderTopWidth: 1,
    borderTopColor: Colors.borderSubtle,
    paddingTop: 17,
    paddingBottom: 40,
    paddingHorizontal: 20,
  },
  feedbackButton: {
    backgroundColor: Colors.buttonPrimaryBg,
    borderRadius: 12,
    height: 48,
    alignItems: 'center',
    justifyContent: 'center',
  },
  feedbackButtonPressed: {
    opacity: 0.8,
  },
  feedbackButtonText: {
    ...Typography.body.ja,
    color: Colors.textInverse,
  },
});
