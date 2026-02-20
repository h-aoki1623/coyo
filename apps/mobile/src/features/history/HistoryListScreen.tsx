import { useCallback, useEffect, useState, useRef } from 'react';
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
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { apiClient } from '@/api/client';
import { Colors } from '@/constants/colors';
import { findTopic } from '@/constants/topics';
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

function HistoryRow({ item, onPress, onDelete }: HistoryRowProps) {
  const translateX = useRef(new Animated.Value(0)).current;
  const [swiped, setSwiped] = useState(false);

  const topic = findTopic(item.topic);
  const topicLabel = topic?.label ?? item.topic;
  const iconBg = topic?.iconBg ?? '#E5E7EB';
  const emoji = topic?.emoji ?? '💬';

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
      'トーク履歴を削除',
      'トーク履歴を削除しますか？この操作は取り消せません。',
      [
        {
          text: 'キャンセル',
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
          text: '削除',
          style: 'destructive',
          onPress: () => onDelete(item.id),
        },
      ],
    );
  }, [translateX, onDelete, item.id]);

  const handleLongPress = useCallback(() => {
    if (!swiped) {
      Animated.spring(translateX, {
        toValue: -80,
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
        accessibilityLabel="Delete conversation"
      >
        <Text style={styles.deleteIcon}>🗑</Text>
      </Pressable>

      <Animated.View
        style={[styles.rowAnimated, { transform: [{ translateX }] }]}
      >
        <Pressable
          style={({ pressed }) => [styles.row, pressed && styles.rowPressed]}
          onPress={handlePress}
          onLongPress={handleLongPress}
          accessibilityRole="button"
          accessibilityLabel={`${topicLabel} conversation, ${formatDuration(item.durationSeconds)}, ${item.totalCorrections} corrections`}
        >
          <View style={styles.rowLeft}>
            <View style={[styles.topicIcon, { backgroundColor: iconBg }]}>
              <Text style={styles.topicEmoji}>{emoji}</Text>
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
}

// -- Main Screen --

export function HistoryListScreen({ navigation }: Props) {
  const [items, setItems] = useState<HistoryListItem[]>([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  // Configure header
  useEffect(() => {
    navigation.setOptions({
      title: 'トーク履歴',
      headerTitleStyle: styles.screenTitle,
    });
  }, [navigation]);

  const fetchHistory = useCallback(
    async (pageNum: number, refresh: boolean = false) => {
      try {
        const result = await apiClient.get<HistoryListResponse>(
          `/api/history?page=${pageNum}&per_page=${PER_PAGE}`,
        );

        if (result.error) {
          Alert.alert('Error', result.error.message);
          return;
        }

        if (result.data) {
          const newItems = result.data.items;
          setItems((prev) => (refresh ? newItems : [...prev, ...newItems]));
          setPage(pageNum);
          setHasMore(pageNum * PER_PAGE < result.data.total);
        }
      } catch {
        Alert.alert(
          'Connection Error',
          'Could not load conversation history.',
        );
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
        Alert.alert('Error', 'Could not delete the conversation.');
      }
    },
    [],
  );

  if (isLoading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color={Colors.primaryBlue} />
      </View>
    );
  }

  if (items.length === 0) {
    return (
      <View style={styles.centerContainer}>
        <Text style={styles.emptyIcon}>💬</Text>
        <Text style={styles.emptyTitle}>No Conversations Yet</Text>
        <Text style={styles.emptySubtitle}>
          Start a conversation from the home screen to see your history here.
        </Text>
      </View>
    );
  }

  const sections = groupByDate(items);

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
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
            tintColor={Colors.primaryBlue}
          />
        }
        onEndReached={handleLoadMore}
        onEndReachedThreshold={0.3}
        ListFooterComponent={
          isLoadingMore ? (
            <View style={styles.footerLoader}>
              <ActivityIndicator size="small" color={Colors.primaryBlue} />
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
    backgroundColor: Colors.background,
  },
  screenTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: Colors.textPrimary,
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: Colors.background,
    paddingHorizontal: 40,
  },
  list: {
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 20,
  },
  // Section headers
  sectionHeader: {
    paddingVertical: 8,
    paddingHorizontal: 4,
  },
  sectionHeaderText: {
    fontSize: 14,
    fontWeight: '600',
    color: Colors.textSecondary,
  },
  // Row
  rowWrapper: {
    marginBottom: 8,
    borderRadius: 14,
    overflow: 'hidden',
  },
  deleteBackground: {
    position: 'absolute',
    right: 0,
    top: 0,
    bottom: 0,
    width: 80,
    backgroundColor: Colors.errorRed,
    justifyContent: 'center',
    alignItems: 'center',
    borderTopRightRadius: 14,
    borderBottomRightRadius: 14,
  },
  deleteIcon: {
    fontSize: 22,
  },
  rowAnimated: {
    backgroundColor: Colors.cardBackground,
    borderRadius: 14,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: Colors.cardBackground,
    borderRadius: 14,
    padding: 14,
    ...Platform.select({
      ios: {
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 1 },
        shadowOpacity: 0.04,
        shadowRadius: 4,
      },
      android: {
        elevation: 1,
      },
    }),
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
    borderRadius: TOPIC_ICON_SIZE / 2,
    justifyContent: 'center',
    alignItems: 'center',
  },
  topicEmoji: {
    fontSize: 18,
  },
  rowInfo: {
    flex: 1,
    gap: 2,
  },
  rowTopic: {
    fontSize: 16,
    fontWeight: '600',
    color: Colors.textPrimary,
  },
  rowMeta: {
    fontSize: 13,
    color: Colors.textSecondary,
  },
  rowRight: {
    marginLeft: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  correctionBadge: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: Colors.primaryBlue,
    justifyContent: 'center',
    alignItems: 'center',
  },
  correctionBadgeText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  // Empty state
  emptyIcon: {
    fontSize: 48,
    marginBottom: 12,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: Colors.textPrimary,
    marginBottom: 8,
  },
  emptySubtitle: {
    fontSize: 14,
    color: Colors.textSecondary,
    textAlign: 'center',
    lineHeight: 20,
  },
  footerLoader: {
    paddingVertical: 20,
    alignItems: 'center',
  },
});
