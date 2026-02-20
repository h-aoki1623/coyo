import { useCallback, useEffect, useState } from 'react';
import {
  View,
  Text,
  FlatList,
  ActivityIndicator,
  Alert,
  StyleSheet,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { apiClient } from '@/api/client';
import { Colors } from '@/constants/colors';
import type { RootStackParamList } from '@/navigation/types';
import type { HistoryDetailResponse, Turn, TurnCorrection, CorrectionItem } from '@/types/conversation';
import { SegmentedControl } from './components/SegmentedControl';
import { formatDuration, formatDetailHeader } from './utils/format';

type Props = NativeStackScreenProps<RootStackParamList, 'HistoryDetail'>;

type LoadingState = 'loading' | 'loaded' | 'error';
const TABS = ['\u30D5\u30A3\u30FC\u30C9\u30D0\u30C3\u30AF', '\u30C1\u30E3\u30C3\u30C8\u5C65\u6B74'] as const;

// -- Chat Bubble (read-only) --

function ChatBubble({ turn, correction }: { turn: Turn; correction?: TurnCorrection }) {
  const isUser = turn.role === 'user';

  return (
    <View>
      <View
        style={[styles.bubbleRow, isUser ? styles.bubbleRowUser : styles.bubbleRowAi]}
        accessibilityRole="text"
        accessibilityLabel={`${isUser ? 'You' : 'Coto'} said: ${turn.text}`}
      >
        {!isUser ? (
          <View style={styles.aiAvatar}>
            <Text style={styles.aiAvatarText}>CO</Text>
          </View>
        ) : null}
        <View style={[styles.bubble, isUser ? styles.bubbleUser : styles.bubbleAi]}>
          <Text style={[styles.bubbleText, isUser ? styles.bubbleTextUser : styles.bubbleTextAi]}>
            {turn.text}
          </Text>
        </View>
      </View>

      {/* Correction annotation under user messages */}
      {isUser ? (
        <CorrectionAnnotation
          correctionStatus={turn.correctionStatus}
          correction={correction}
        />
      ) : null}
    </View>
  );
}

function CorrectionAnnotation({
  correctionStatus,
  correction,
}: {
  correctionStatus: Turn['correctionStatus'];
  correction?: TurnCorrection;
}) {
  if (correctionStatus === 'none' || correctionStatus === 'pending') return null;

  if (correctionStatus === 'clean') {
    return (
      <View style={styles.annotationRow}>
        <Text style={styles.cleanIcon}>✓</Text>
        <Text style={styles.cleanText}>No corrections</Text>
      </View>
    );
  }

  const count = correction?.items.length ?? 0;
  return (
    <View style={styles.annotationRow}>
      <Text style={styles.warningIcon}>⚠</Text>
      <Text style={styles.correctionCountText}>
        {count} correction{count !== 1 ? 's' : ''} ›
      </Text>
    </View>
  );
}

// -- Feedback Card --

function DetailCorrectionCard({ correction }: { correction: TurnCorrection }) {
  return (
    <View style={styles.correctionCard}>
      {correction.items.map((item) => (
        <DetailCorrectionItem key={item.id} item={item} />
      ))}
    </View>
  );
}

function DetailCorrectionItem({ item }: { item: CorrectionItem }) {
  return (
    <View style={styles.correctionItemContainer}>
      {/* Original sentence with error highlighted */}
      <Text style={styles.sentenceText}>
        {renderHighlighted(item.originalSentence, item.original, 'original')}
      </Text>

      {/* Corrected sentence with correction highlighted */}
      <Text style={styles.sentenceText}>
        {renderHighlighted(item.correctedSentence, item.corrected, 'corrected')}
      </Text>

      {/* Explanation */}
      <View style={styles.explanationRow}>
        <Text style={styles.explanationDiamond}>◇</Text>
        <Text style={styles.explanationText}>{item.explanation}</Text>
      </View>
    </View>
  );
}

function renderHighlighted(
  sentence: string,
  target: string,
  type: 'original' | 'corrected',
): React.ReactNode[] {
  const index = sentence.indexOf(target);
  if (index === -1) {
    return [<Text key="plain">{sentence}</Text>];
  }

  const before = sentence.slice(0, index);
  const after = sentence.slice(index + target.length);
  const highlightStyle = type === 'original' ? styles.errorHighlight : styles.greenHighlight;

  return [
    before ? <Text key="before">{before}</Text> : null,
    <Text key="highlight" style={highlightStyle}>{target}</Text>,
    after ? <Text key="after">{after}</Text> : null,
  ].filter(Boolean);
}

// -- Tab Content Components --

function FeedbackTab({ corrections }: { corrections: TurnCorrection[] }) {
  if (corrections.length === 0) {
    return (
      <View style={styles.emptyTab}>
        <Text style={styles.emptyCheckIcon}>✓</Text>
        <Text style={styles.emptyTabTitle}>Perfect!</Text>
        <Text style={styles.emptyTabText}>No corrections were needed.</Text>
      </View>
    );
  }

  return (
    <FlatList
      data={corrections}
      renderItem={({ item }) => <DetailCorrectionCard correction={item} />}
      keyExtractor={(item) => item.id}
      contentContainerStyle={styles.correctionsList}
      showsVerticalScrollIndicator={false}
    />
  );
}

function ChatHistoryTab({
  turns,
  corrections,
  durationLabel,
}: {
  turns: Turn[];
  corrections: TurnCorrection[];
  durationLabel: string;
}) {
  // Build a lookup from turnId to correction
  const correctionMap: Record<string, TurnCorrection> = {};
  for (const c of corrections) {
    correctionMap[c.turnId] = c;
  }

  if (turns.length === 0) {
    return (
      <View style={styles.emptyTab}>
        <Text style={styles.emptyTabText}>No messages in this conversation.</Text>
      </View>
    );
  }

  return (
    <FlatList
      data={turns}
      renderItem={({ item }) => (
        <ChatBubble turn={item} correction={correctionMap[item.id]} />
      )}
      keyExtractor={(item) => item.id}
      contentContainerStyle={styles.turnsList}
      showsVerticalScrollIndicator={false}
      ListFooterComponent={
        <View style={styles.chatFooter}>
          <Text style={styles.chatFooterText}>トーク終了 · {durationLabel}</Text>
        </View>
      }
    />
  );
}

// -- Main Screen --

export function HistoryDetailScreen({ navigation, route }: Props) {
  const { conversationId } = route.params;
  const [detail, setDetail] = useState<HistoryDetailResponse | null>(null);
  const [loadingState, setLoadingState] = useState<LoadingState>('loading');
  const [selectedTab, setSelectedTab] = useState(0);

  const fetchDetail = useCallback(async () => {
    setLoadingState('loading');
    try {
      const result = await apiClient.get<HistoryDetailResponse>(
        `/api/history/${conversationId}`,
      );

      if (result.error) {
        Alert.alert('Error', result.error.message);
        setLoadingState('error');
        return;
      }

      if (result.data) {
        setDetail(result.data);
      }
      setLoadingState('loaded');
    } catch {
      Alert.alert(
        'Connection Error',
        'Could not load conversation details.',
      );
      setLoadingState('error');
    }
  }, [conversationId]);

  useEffect(() => {
    fetchDetail();
  }, [fetchDetail]);

  // Set header title
  useEffect(() => {
    if (detail) {
      const headerText = formatDetailHeader(detail.startedAt, detail.durationSeconds);
      navigation.setOptions({
        title: '',
        headerTitle: () => (
          <Text style={styles.headerTitleText}>{headerText}</Text>
        ),
      });
    }
  }, [navigation, detail]);

  if (loadingState === 'loading') {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color={Colors.primaryBlue} />
      </View>
    );
  }

  if (loadingState === 'error' || !detail) {
    return (
      <View style={styles.centerContainer}>
        <Text style={styles.errorText}>Could not load details</Text>
      </View>
    );
  }

  const durationLabel = formatDuration(detail.durationSeconds);
  // Cast: backend guarantees role/correctionStatus/type are valid union values
  const turns = (detail.turns ?? []) as Turn[];
  const corrections = (detail.corrections ?? []) as TurnCorrection[];

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <SegmentedControl
        tabs={TABS}
        selectedIndex={selectedTab}
        onSelect={setSelectedTab}
      />
      {selectedTab === 0 ? (
        <FeedbackTab corrections={corrections} />
      ) : (
        <ChatHistoryTab
          turns={turns}
          corrections={corrections}
          durationLabel={durationLabel}
        />
      )}
    </SafeAreaView>
  );
}

const AI_AVATAR_SIZE = 24;

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: Colors.background,
  },
  errorText: {
    fontSize: 16,
    color: Colors.textSecondary,
  },
  headerTitleText: {
    fontSize: 14,
    fontWeight: '500',
    color: Colors.textSecondary,
    textAlign: 'center',
  },
  // Chat bubbles
  turnsList: {
    paddingTop: 12,
    paddingBottom: 16,
  },
  bubbleRow: {
    paddingHorizontal: 16,
    paddingVertical: 4,
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 8,
  },
  bubbleRowUser: {
    justifyContent: 'flex-end',
  },
  bubbleRowAi: {
    justifyContent: 'flex-start',
  },
  aiAvatar: {
    width: AI_AVATAR_SIZE,
    height: AI_AVATAR_SIZE,
    borderRadius: AI_AVATAR_SIZE / 2,
    backgroundColor: Colors.primaryBlue,
    justifyContent: 'center',
    alignItems: 'center',
  },
  aiAvatarText: {
    fontSize: 8,
    fontWeight: '800',
    color: '#FFFFFF',
    letterSpacing: 0.5,
  },
  bubble: {
    maxWidth: '75%',
    borderRadius: 18,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  bubbleUser: {
    backgroundColor: Colors.primaryBlue,
    borderBottomRightRadius: 4,
  },
  bubbleAi: {
    backgroundColor: Colors.aiBubbleBg,
    borderBottomLeftRadius: 4,
  },
  bubbleText: {
    fontSize: 15,
    lineHeight: 21,
  },
  bubbleTextUser: {
    color: '#FFFFFF',
  },
  bubbleTextAi: {
    color: Colors.textPrimary,
  },
  // Correction annotations (chat history tab)
  annotationRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingTop: 2,
    paddingRight: 16,
    justifyContent: 'flex-end',
  },
  cleanIcon: {
    fontSize: 12,
    color: Colors.correctionGreen,
    fontWeight: '700',
  },
  cleanText: {
    fontSize: 12,
    color: Colors.correctionGreen,
    fontWeight: '500',
  },
  warningIcon: {
    fontSize: 12,
    color: Colors.correctionOrange,
  },
  correctionCountText: {
    fontSize: 12,
    color: Colors.correctionOrange,
    fontWeight: '600',
  },
  // Chat footer
  chatFooter: {
    alignItems: 'center',
    paddingVertical: 20,
  },
  chatFooterText: {
    fontSize: 14,
    color: Colors.textSecondary,
  },
  // Corrections list (feedback tab)
  correctionsList: {
    padding: 16,
    gap: 12,
  },
  correctionCard: {
    backgroundColor: Colors.cardBackground,
    borderRadius: 14,
    padding: 16,
    gap: 16,
    ...Platform.select({
      ios: {
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 1 },
        shadowOpacity: 0.06,
        shadowRadius: 6,
      },
      android: {
        elevation: 2,
      },
    }),
  },
  correctionItemContainer: {
    gap: 8,
  },
  sentenceText: {
    fontSize: 15,
    lineHeight: 22,
    color: Colors.textPrimary,
  },
  errorHighlight: {
    color: Colors.errorRed,
    textDecorationLine: 'line-through',
  },
  greenHighlight: {
    color: Colors.correctionGreen,
    fontWeight: '600',
    backgroundColor: '#DCFCE7',
  },
  explanationRow: {
    flexDirection: 'row',
    gap: 6,
    paddingTop: 2,
  },
  explanationDiamond: {
    fontSize: 12,
    color: Colors.textSecondary,
    marginTop: 1,
  },
  explanationText: {
    fontSize: 13,
    color: Colors.textSecondary,
    lineHeight: 18,
    flex: 1,
  },
  // Empty states
  emptyTab: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 40,
  },
  emptyCheckIcon: {
    fontSize: 40,
    color: Colors.correctionGreen,
    fontWeight: '700',
    marginBottom: 12,
  },
  emptyTabTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: Colors.textPrimary,
    marginBottom: 8,
  },
  emptyTabText: {
    fontSize: 14,
    color: Colors.textSecondary,
    textAlign: 'center',
  },
});
