import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View,
  Text,
  FlatList,
  ActivityIndicator,
  Alert,
  StyleSheet,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { apiClient } from '@/api/client';
import { Colors } from '@/constants/colors';
import { Typography } from '@/constants/typography';
import { t } from '@/i18n';
import { NavBar } from '@/components/NavBar';
import { EmptyFeedbackState } from '@/components/EmptyFeedbackState';
import { CorrectionFeedbackCard } from '@/components/CorrectionFeedbackCard';
import { groupCorrectionsBySentence } from '@/utils/group-corrections';
import { MessageBubble } from '@/features/talk/components/MessageBubble';
import type { RootStackParamList } from '@/navigation/types';
import type { HistoryDetailResponse, Turn, TurnCorrection } from '@/types/conversation';
import { SegmentedControl } from './components/SegmentedControl';
import { formatDuration, formatDetailHeader } from './utils/format';

type Props = NativeStackScreenProps<RootStackParamList, 'HistoryDetail'>;

type LoadingState = 'loading' | 'loaded' | 'error';

// -- Tab Content Components --

function FeedbackTab({ corrections }: { corrections: TurnCorrection[] }) {
  const sentenceGroups = useMemo(
    () => groupCorrectionsBySentence(corrections),
    [corrections],
  );

  if (sentenceGroups.length === 0) {
    return (
      <View style={styles.emptyTab}>
        <EmptyFeedbackState />
      </View>
    );
  }

  return (
    <FlatList
      data={sentenceGroups}
      renderItem={({ item }) => <CorrectionFeedbackCard sentenceCorrection={item} />}
      keyExtractor={(item) => item.key}
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
        <Text style={styles.emptyTabText}>{t('historyDetail.emptyChatHistory')}</Text>
      </View>
    );
  }

  return (
    <FlatList
      data={turns}
      renderItem={({ item }) => (
        <MessageBubble turn={item} correction={correctionMap[item.id]} />
      )}
      keyExtractor={(item) => item.id}
      contentContainerStyle={styles.turnsList}
      showsVerticalScrollIndicator={false}
      ListFooterComponent={
        <View style={styles.chatFooter}>
          <Text style={styles.chatFooterText}>
            {t('historyDetail.chatEndLabel', { duration: durationLabel })}
          </Text>
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

  const tabs = [t('historyDetail.tabFeedback'), t('historyDetail.tabChatHistory')];

  const fetchDetail = useCallback(async () => {
    setLoadingState('loading');
    try {
      const result = await apiClient.get<HistoryDetailResponse>(
        `/api/history/${conversationId}`,
      );

      if (result.error) {
        Alert.alert(t('errors.genericError'), result.error.message);
        setLoadingState('error');
        return;
      }

      if (result.data) {
        setDetail(result.data);
      }
      setLoadingState('loaded');
    } catch {
      Alert.alert(t('errors.connectionTitle'), t('errors.loadDetailError'));
      setLoadingState('error');
    }
  }, [conversationId]);

  useEffect(() => {
    fetchDetail();
  }, [fetchDetail]);

  useEffect(() => {
    navigation.setOptions({ headerShown: false });
  }, [navigation]);

  const handleBack = useCallback(() => navigation.goBack(), [navigation]);

  if (loadingState === 'loading') {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color={Colors.buttonPrimaryBg} />
      </View>
    );
  }

  if (loadingState === 'error' || !detail) {
    return (
      <View style={styles.centerContainer}>
        <Text style={styles.errorText}>{t('historyDetail.errorLoadDetail')}</Text>
      </View>
    );
  }

  const durationLabel = formatDuration(detail.durationSeconds);
  const metaLabel = formatDetailHeader(detail.startedAt, detail.durationSeconds);
  // Cast: backend guarantees role/correctionStatus/type are valid union values
  const turns = (detail.turns ?? []) as Turn[];
  const corrections = (detail.corrections ?? []) as TurnCorrection[];

  return (
    <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
      <NavBar title={t('historyDetail.title')} onBack={handleBack} />
      <View style={styles.metaContainer}>
        <Text style={styles.metaText}>{metaLabel}</Text>
      </View>
      <SegmentedControl
        tabs={tabs}
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

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.surfacePrimary,
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: Colors.surfacePrimary,
  },
  errorText: {
    ...Typography.body.ja,
    color: Colors.textSecondary,
  },
  metaContainer: {
    alignItems: 'center',
    paddingTop: 6,
    paddingBottom: 12,
  },
  metaText: {
    ...Typography.captionSmall.ja,
    color: Colors.textTertiary,
    textAlign: 'center',
  },
  // Chat history
  turnsList: {
    paddingTop: 16,
    paddingBottom: 16,
    gap: 16,
  },
  // Chat footer
  chatFooter: {
    alignItems: 'center',
    paddingTop: 14,
    paddingBottom: 13,
  },
  chatFooterText: {
    ...Typography.bodySmall.ja,
    color: Colors.textTertiary,
  },
  // Corrections list (feedback tab)
  correctionsList: {
    paddingHorizontal: 20,
    paddingVertical: 16,
    gap: 12,
  },
  // Empty states
  emptyTab: {
    flex: 1,
    alignItems: 'center',
    paddingTop: 32,
    paddingHorizontal: 20,
  },
  emptyTabText: {
    ...Typography.bodySmall.ja,
    color: Colors.textSecondary,
    textAlign: 'center',
  },
});
