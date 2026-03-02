import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View,
  Text,
  FlatList,
  Pressable,
  ActivityIndicator,
  StyleSheet,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { apiClient } from '@/api/client';
import { Colors } from '@/constants/colors';
import { Fonts, Typography } from '@/constants/typography';
import { t } from '@/i18n';
import { NavBar } from '@/components/NavBar';
import { EmptyFeedbackState } from '@/components/EmptyFeedbackState';
import { CorrectionFeedbackCard } from '@/components/CorrectionFeedbackCard';
import { groupCorrectionsBySentence } from '@/utils/group-corrections';
import { useConversationStore } from '@/stores/conversation-store';
import type { RootStackParamList } from '@/navigation/types';
import type { FeedbackResponse, TurnCorrection } from '@/types/conversation';

type Props = NativeStackScreenProps<RootStackParamList, 'Feedback'>;

type LoadingState = 'loading' | 'loaded' | 'error';

// -- Summary Stats Component --

interface SummaryStatsProps {
  totalTurns: number;
  totalCorrections: number;
  totalClean: number;
}

function SummaryStats({ totalTurns, totalCorrections, totalClean }: SummaryStatsProps) {
  return (
    <View style={styles.statsRow}>
      <StatCircle value={totalTurns} label={t('feedback.statExchanges')} color={Colors.textPrimary} />
      <StatCircle value={totalCorrections} label={t('feedback.statCorrections')} color={Colors.statusWarning} />
      <StatCircle value={totalClean} label={t('feedback.statClean')} color={Colors.statusSuccess} />
    </View>
  );
}

function StatCircle({
  value,
  label,
  color,
}: {
  value: number;
  label: string;
  color: string;
}) {
  return (
    <View
      style={styles.statItem}
      accessibilityLabel={`${value} ${label}`}
    >
      <Text style={[styles.statValue, { color }]}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

function ListItemSeparator() {
  return <View style={styles.listSeparator} />;
}

// -- Main Screen --

export function FeedbackScreen({ navigation, route }: Props) {
  const { conversationId } = route.params;
  const [corrections, setCorrections] = useState<TurnCorrection[]>([]);
  const [stats, setStats] = useState({ totalTurns: 0, totalCorrections: 0, totalClean: 0 });
  const [loadingState, setLoadingState] = useState<LoadingState>('loading');
  const reset = useConversationStore((s) => s.reset);

  const fetchFeedback = useCallback(async () => {
    setLoadingState('loading');
    try {
      const result = await apiClient.get<FeedbackResponse>(
        `/api/conversations/${conversationId}/feedback`,
      );

      if (result.error) {
        setLoadingState('error');
        return;
      }

      if (result.data) {
        // Cast: backend guarantees correction item types are valid union values
        setCorrections((result.data.corrections ?? []) as TurnCorrection[]);
        setStats({
          totalTurns: result.data.totalTurns ?? 0,
          totalCorrections: result.data.totalCorrections ?? 0,
          totalClean: result.data.totalClean ?? 0,
        });
      }
      setLoadingState('loaded');
    } catch {
      setLoadingState('error');
    }
  }, [conversationId]);

  useEffect(() => {
    fetchFeedback();
  }, [fetchFeedback]);

  const sentenceGroups = useMemo(
    () => groupCorrectionsBySentence(corrections),
    [corrections],
  );

  const handleBackToHome = useCallback(() => {
    reset();
    navigation.popToTop();
  }, [reset, navigation]);

  return (
    <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
      <NavBar title={t('feedback.title')} />
      {loadingState === 'loading' ? (
        <View style={styles.centerContent}>
          <ActivityIndicator size="large" color={Colors.buttonPrimaryBg} />
          <Text style={styles.loadingText}>{t('feedback.loading')}</Text>
        </View>
      ) : loadingState === 'error' ? (
        <View style={styles.centerContent}>
          <Text style={styles.errorIcon}>!</Text>
          <Text style={styles.errorTitle}>{t('feedback.errorTitle')}</Text>
          <Pressable
            style={styles.retryButton}
            onPress={fetchFeedback}
            accessibilityRole="button"
            accessibilityLabel={t('feedback.retry')}
          >
            <Text style={styles.retryButtonText}>{t('feedback.retry')}</Text>
          </Pressable>
        </View>
      ) : (
        <>
          <FlatList
            data={sentenceGroups}
            renderItem={({ item }) => <CorrectionFeedbackCard sentenceCorrection={item} />}
            keyExtractor={(item) => item.key}
            contentContainerStyle={styles.list}
            showsVerticalScrollIndicator={false}
            ItemSeparatorComponent={ListItemSeparator}
            ListHeaderComponent={
              <View style={styles.listHeader}>
                <SummaryStats
                  totalTurns={stats.totalTurns}
                  totalCorrections={stats.totalCorrections}
                  totalClean={stats.totalClean}
                />
              </View>
            }
            ListEmptyComponent={
              <View style={styles.emptyContainer}>
                <EmptyFeedbackState />
              </View>
            }
          />
          <View style={styles.bottomBar}>
            <Pressable
              style={({ pressed }) => [
                styles.homeButton,
                pressed && styles.homeButtonPressed,
              ]}
              onPress={handleBackToHome}
              testID="go-home"
              accessibilityRole="button"
              accessibilityLabel={t('feedback.goHome')}
            >
              <Text style={styles.homeButtonText}>{t('feedback.goHome')}</Text>
            </Pressable>
          </View>
        </>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.surfacePrimary,
  },
  centerContent: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 40,
  },
  loadingText: {
    ...Typography.body.ja,
    marginTop: 12,
    color: Colors.textSecondary,
  },
  // Error state
  errorIcon: {
    fontSize: 36,
    fontFamily: Fonts.plusJakartaSans.bold,
    color: Colors.statusError,
    marginBottom: 12,
    textAlign: 'center',
    width: 56,
    height: 56,
    lineHeight: 56,
    borderRadius: 28,
    backgroundColor: Colors.statusErrorBg,
    overflow: 'hidden',
  },
  errorTitle: {
    ...Typography.headline.ja,
    color: Colors.textPrimary,
    marginBottom: 20,
  },
  retryButton: {
    backgroundColor: Colors.buttonPrimaryBg,
    paddingHorizontal: 32,
    paddingVertical: 14,
    borderRadius: 12,
    minWidth: 180,
    alignItems: 'center',
  },
  retryButtonText: {
    ...Typography.body.ja,
    color: Colors.surfaceCard,
  },
  // Stats
  statsRow: {
    flexDirection: 'row',
    gap: 12,
  },
  statItem: {
    flex: 1,
    height: 95,
    borderWidth: 1,
    borderColor: Colors.borderDefault,
    borderRadius: 14,
    paddingHorizontal: 9,
    paddingVertical: 17,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.surfaceCard,
  },
  statValue: {
    ...Typography.display.en,
  },
  statLabel: {
    ...Typography.caption.ja,
    color: Colors.textTertiary,
    textAlign: 'center',
    marginTop: 4,
  },
  // List
  listSeparator: {
    height: 12,
  },
  list: {
    paddingHorizontal: 20,
    paddingTop: 0,
    paddingBottom: 16,
  },
  listHeader: {
    marginBottom: 20,
  },
  // Empty state (no corrections)
  emptyContainer: {
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingTop: 32,
  },
  // Bottom bar
  bottomBar: {
    paddingHorizontal: 20,
    paddingTop: 17,
    paddingBottom: 40,
    borderTopWidth: 1,
    borderTopColor: Colors.borderSubtle,
    backgroundColor: Colors.surfacePrimary,
  },
  homeButton: {
    borderWidth: 1,
    borderColor: Colors.buttonGhostBorder,
    height: 48,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  homeButtonPressed: {
    backgroundColor: Colors.accentBg,
  },
  homeButtonText: {
    ...Typography.body.ja,
    color: Colors.buttonGhostText,
  },
});
