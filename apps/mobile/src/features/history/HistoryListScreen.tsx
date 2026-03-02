import { memo, useCallback, useEffect, useState, useRef } from 'react';
import {
  View,
  Text,
  SectionList,
  Pressable,
  ActivityIndicator,
  RefreshControl,
  Alert,
  Animated,
  StyleSheet,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { apiClient } from '@/api/client';
import { Colors } from '@/constants/colors';
import { Typography } from '@/constants/typography';
import { t } from '@/i18n';
import { findTopic } from '@/constants/topics';
import { TopicIcon, TrashIcon, SpeechBubbleIcon, HintCircleIcon } from '@/components/icons';
import { NavBar } from '@/components/NavBar';
import type { RootStackParamList } from '@/navigation/types';
import type { HistoryListItem, HistoryListResponse } from '@/types/conversation';
import { formatDuration, formatTime, groupByDate } from './utils/format';

type Props = NativeStackScreenProps<RootStackParamList, 'HistoryList'>;

const PER_PAGE = 20;

// -- Row Component --

interface HistoryRowProps {
  item: HistoryListItem;
  onPress: (id: string) => void;
  onDelete: (id: string) => void;
}

const HistoryRow = memo(function HistoryRow({ item, onPress, onDelete }: HistoryRowProps) {
  const translateX = useRef(new Animated.Value(0)).current;
  const [swiped, setSwiped] = useState(false);

  const topic = findTopic(item.topic);
  const topicLabel = topic?.label ?? item.topic;
  const topicIcon = topic?.icon ?? 'globe';
  const topicIconColor = topic?.iconColor ?? Colors.topicSports;

  const handlePress = useCallback(() => {
    if (swiped) {
      // Reset swipe when tapping
      Animated.spring(translateX, {
        toValue: 0,
        useNativeDriver: true,
      }).start();
      setSwiped(false);
    } else {
      onPress(item.id);
    }
  }, [swiped, translateX, onPress, item.id]);

  const handleSwipeDelete = useCallback(() => {
    Alert.alert(
      t('history.deleteTitle'),
      t('history.deleteMessage'),
      [
        {
          text: t('history.deleteCancel'),
          style: 'cancel',
          onPress: () => {
            Animated.spring(translateX, {
              toValue: 0,
              useNativeDriver: true,
            }).start();
            setSwiped(false);
          },
        },
        {
          text: t('history.deleteConfirm'),
          style: 'destructive',
          onPress: () => onDelete(item.id),
        },
      ],
    );
  }, [translateX, onDelete, item.id]);

  const handleLongPress = useCallback(() => {
    if (!swiped) {
      Animated.spring(translateX, {
        toValue: -50,
        useNativeDriver: true,
      }).start();
      setSwiped(true);
    }
  }, [swiped, translateX]);

  return (
    <View style={styles.rowWrapper}>
      {/* Delete background */}
      <Pressable
        style={styles.deleteBackground}
        onPress={handleSwipeDelete}
        accessibilityRole="button"
        accessibilityLabel={t('history.deleteConfirm')}
      >
        <TrashIcon size={20} color={Colors.surfaceCard} />
      </Pressable>

      <Animated.View
        style={[styles.rowAnimated, { transform: [{ translateX }] }]}
      >
        <Pressable
          style={({ pressed }) => [styles.row, pressed && styles.rowPressed]}
          onPress={handlePress}
          onLongPress={handleLongPress}
          accessibilityRole="button"
          accessibilityLabel={`${topicLabel}, ${formatDuration(item.durationSeconds)}`}
        >
          <View style={styles.rowLeft}>
            <View style={styles.topicIcon}>
              <TopicIcon icon={topicIcon} size={20} color={topicIconColor} />
            </View>
            <View style={styles.rowInfo}>
              <Text style={styles.rowTopic}>{topicLabel}</Text>
              <Text style={styles.rowMeta}>
                {formatDuration(item.durationSeconds)} · {formatTime(item.startedAt)}
              </Text>
            </View>
          </View>
          <View style={styles.rowRight}>
            {item.totalCorrections > 0 ? (
              <View style={styles.correctionBadge}>
                <Text style={styles.correctionBadgeText}>
                  {item.totalCorrections}
                </Text>
              </View>
            ) : null}
          </View>
        </Pressable>
      </Animated.View>
    </View>
  );
});

// -- Main Screen --

export function HistoryListScreen({ navigation }: Props) {
  const [items, setItems] = useState<HistoryListItem[]>([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  useEffect(() => {
    navigation.setOptions({ headerShown: false });
  }, [navigation]);

  const fetchHistory = useCallback(
    async (pageNum: number, refresh: boolean = false) => {
      try {
        const result = await apiClient.get<HistoryListResponse>(
          `/api/history?page=${pageNum}&per_page=${PER_PAGE}`,
        );

        if (result.error) {
          Alert.alert(t('errors.genericError'), result.error.message);
          return;
        }

        if (result.data) {
          const newItems = result.data.items;
          setItems((prev) => (refresh ? newItems : [...prev, ...newItems]));
          setPage(pageNum);
          setHasMore(pageNum * PER_PAGE < result.data.total);
        }
      } catch {
        Alert.alert(t('errors.connectionTitle'), t('errors.loadHistoryError'));
      }
    },
    [],
  );

  useEffect(() => {
    const load = async () => {
      setIsLoading(true);
      await fetchHistory(1, true);
      setIsLoading(false);
    };
    load();
  }, [fetchHistory]);

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    await fetchHistory(1, true);
    setIsRefreshing(false);
  }, [fetchHistory]);

  const handleLoadMore = useCallback(async () => {
    if (!hasMore || isLoadingMore) return;
    setIsLoadingMore(true);
    await fetchHistory(page + 1, false);
    setIsLoadingMore(false);
  }, [hasMore, isLoadingMore, page, fetchHistory]);

  const handleRowPress = useCallback(
    (conversationId: string) => {
      navigation.navigate('HistoryDetail', { conversationId });
    },
    [navigation],
  );

  const handleDelete = useCallback(
    async (conversationId: string) => {
      try {
        await apiClient.delete(`/api/history/${conversationId}`);
        setItems((prev) => prev.filter((item) => item.id !== conversationId));
      } catch {
        Alert.alert(t('errors.genericError'), t('errors.deleteError'));
      }
    },
    [],
  );

  const handleBack = useCallback(() => navigation.goBack(), [navigation]);

  if (isLoading) {
    return (
      <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
        <NavBar title={t('history.title')} onBack={handleBack} testID="history-title" />
        <View style={styles.centerContainer}>
          <ActivityIndicator size="large" color={Colors.buttonPrimaryBg} />
        </View>
      </SafeAreaView>
    );
  }

  if (items.length === 0) {
    return (
      <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
        <NavBar title={t('history.title')} onBack={handleBack} testID="history-title" />
        <View style={styles.emptyContainer}>
          <View style={styles.emptyIconContainer}>
            <SpeechBubbleIcon size={38} color={Colors.textTertiary} />
          </View>
          <Text style={styles.emptyTitle}>{t('history.emptyTitle')}</Text>
          <Text style={styles.emptySubtitle}>{t('history.emptySubtitle')}</Text>
          <View style={styles.infoCard}>
            <View style={styles.infoCardIcon}>
              <HintCircleIcon size={16} color={Colors.buttonGhostText} />
            </View>
            <Text style={styles.infoCardText}>{t('history.emptyHint')}</Text>
          </View>
        </View>
      </SafeAreaView>
    );
  }

  const sections = groupByDate(items);

  return (
    <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
      <NavBar title={t('history.title')} onBack={handleBack} testID="history-title" />
      <SectionList
        sections={sections}
        renderItem={({ item }) => (
          <HistoryRow
            item={item}
            onPress={handleRowPress}
            onDelete={handleDelete}
          />
        )}
        renderSectionHeader={({ section }) => (
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionHeaderText}>{section.title}</Text>
          </View>
        )}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.list}
        showsVerticalScrollIndicator={false}
        stickySectionHeadersEnabled={false}
        refreshControl={
          <RefreshControl
            refreshing={isRefreshing}
            onRefresh={handleRefresh}
            tintColor={Colors.buttonPrimaryBg}
          />
        }
        onEndReached={handleLoadMore}
        onEndReachedThreshold={0.3}
        ListFooterComponent={
          isLoadingMore ? (
            <View style={styles.footerLoader}>
              <ActivityIndicator size="small" color={Colors.buttonPrimaryBg} />
            </View>
          ) : null
        }
      />
    </SafeAreaView>
  );
}

const TOPIC_ICON_SIZE = 40;

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.surfacePrimary,
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 40,
  },
  list: {
    paddingHorizontal: 0,
    paddingTop: 0,
    paddingBottom: 20,
  },
  // Section headers
  sectionHeader: {
    paddingTop: 24,
    paddingBottom: 12,
    paddingHorizontal: 20,
  },
  sectionHeaderText: {
    ...Typography.captionSmall.ja,
    color: Colors.textTertiary,
  },
  // Row
  rowWrapper: {
    overflow: 'hidden',
  },
  deleteBackground: {
    position: 'absolute',
    right: 0,
    top: 0,
    bottom: 0,
    width: 50,
    backgroundColor: Colors.statusError,
    justifyContent: 'center',
    alignItems: 'center',
  },
  rowAnimated: {
    backgroundColor: Colors.surfacePrimary,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    height: 69,
    paddingHorizontal: 20,
    paddingTop: 12,
    paddingBottom: 13,
    borderBottomWidth: 1,
    borderBottomColor: Colors.borderSubtle,
  },
  rowPressed: {
    opacity: 0.7,
  },
  rowLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    flex: 1,
  },
  topicIcon: {
    width: TOPIC_ICON_SIZE,
    height: TOPIC_ICON_SIZE,
    borderRadius: 12,
    backgroundColor: Colors.borderSubtle,
    justifyContent: 'center',
    alignItems: 'center',
  },
  rowInfo: {
    flex: 1,
    gap: 2,
  },
  rowTopic: {
    ...Typography.bodyLarge.ja,
    color: Colors.textPrimary,
  },
  rowMeta: {
    ...Typography.captionSmall.ja,
    color: Colors.textTertiary,
  },
  rowRight: {
    marginLeft: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  correctionBadge: {
    backgroundColor: Colors.borderSubtle,
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 4,
    justifyContent: 'center',
    alignItems: 'center',
  },
  correctionBadgeText: {
    ...Typography.captionSmall.en,
    color: Colors.statusWarning,
  },
  // Empty state
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingBottom: 80,
    backgroundColor: Colors.surfacePrimary,
  },
  emptyIconContainer: {
    width: 80,
    height: 80,
    borderRadius: 24,
    backgroundColor: Colors.borderSubtle,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 20,
  },
  emptyTitle: {
    ...Typography.title.ja,
    color: Colors.textPrimary,
    letterSpacing: -0.3,
    textAlign: 'center',
    marginBottom: 12,
  },
  emptySubtitle: {
    ...Typography.caption.ja,
    color: Colors.textSecondary,
    textAlign: 'center',
    marginBottom: 24,
    maxWidth: 248,
  },
  infoCard: {
    flexDirection: 'row',
    backgroundColor: Colors.accentBg,
    borderWidth: 1,
    borderColor: Colors.accentBorder,
    borderRadius: 14,
    padding: 16,
    gap: 12,
    alignItems: 'flex-start',
    width: '100%',
  },
  infoCardIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: Colors.accentBorder,
    justifyContent: 'center',
    alignItems: 'center',
  },
  infoCardText: {
    ...Typography.caption.ja,
    flex: 1,
    color: Colors.buttonGhostText,
  },
  footerLoader: {
    paddingVertical: 20,
    alignItems: 'center',
  },
});
