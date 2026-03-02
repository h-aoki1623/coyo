import { useCallback, useState, memo, useMemo } from 'react';
import {
  View,
  Text,
  FlatList,
  Pressable,
  Alert,
  ActivityIndicator,
  StyleSheet,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { apiClient } from '@/api/client';
import { getTopics } from '@/constants/topics';
import { Colors } from '@/constants/colors';
import { Typography } from '@/constants/typography';
import { t } from '@/i18n';
import { useConversationStore } from '@/stores/conversation-store';
import { useAppStore } from '@/stores/app-store';
import { LogoIcon, HistoryIcon, TopicIcon, ResumeIcon } from '@/components/icons';
import type { RootStackParamList, TopicKey } from '@/navigation/types';
import type { Topic } from '@/constants/topics';

type Props = NativeStackScreenProps<RootStackParamList, 'Home'>;

interface CreateConversationResponse {
  id: string;
  topic: string;
  status: string;
}

interface PausedBannerProps {
  onResume: () => void;
  isResuming: boolean;
}

function PausedConversationBanner({ onResume, isResuming }: PausedBannerProps) {
  return (
    <View style={styles.pausedBanner}>
      <View style={styles.pausedLeft}>
        <View style={styles.pausedPlayIcon}>
          <ResumeIcon size={22} color={Colors.buttonPrimaryBg} />
        </View>
        <View>
          <Text style={styles.pausedTitle}>{t('home.pausedBanner.title')}</Text>
          <Text style={styles.pausedTimestamp}>{t('home.pausedBanner.hint')}</Text>
        </View>
      </View>
      <Pressable
        onPress={onResume}
        disabled={isResuming}
        style={styles.resumeButton}
        accessibilityRole="button"
        accessibilityLabel={t('home.pausedBanner.resume')}
      >
        {isResuming ? (
          <ActivityIndicator size="small" color={Colors.buttonPrimaryBg} />
        ) : (
          <Text style={styles.resumeText}>{t('home.pausedBanner.resume')}</Text>
        )}
      </Pressable>
    </View>
  );
}

interface TopicCardProps {
  topic: Topic;
  isLoading: boolean;
  isDisabled: boolean;
  onPress: (key: TopicKey) => void;
}

const TopicCard = memo(function TopicCard({ topic, isLoading, isDisabled, onPress }: TopicCardProps) {
  return (
    <Pressable
      style={({ pressed }) => [
        styles.card,
        pressed && styles.cardPressed,
        isDisabled && !isLoading && styles.cardDisabled,
      ]}
      onPress={() => onPress(topic.key)}
      disabled={isDisabled}
      testID={`topic-${topic.key}`}
      accessibilityRole="button"
      accessibilityLabel={topic.label}
    >
      <View style={styles.cardContent}>
        <View style={[styles.iconContainer, { backgroundColor: topic.iconBg }]}>
          <TopicIcon icon={topic.icon} size={20} color={topic.iconColor} />
        </View>
        <Text style={styles.topicLabel}>{topic.label}</Text>
      </View>
      <View style={styles.cardRight}>
        {isLoading ? (
          <ActivityIndicator size="small" color={Colors.buttonPrimaryBg} />
        ) : (
          <Text style={styles.chevron}>{'\u203A'}</Text>
        )}
      </View>
    </Pressable>
  );
});

export function HomeScreen({ navigation }: Props) {
  const [loadingTopic, setLoadingTopic] = useState<TopicKey | null>(null);
  const [isResuming, setIsResuming] = useState(false);
  const startConversation = useConversationStore((s) => s.startConversation);
  const pausedConversationId = useAppStore((s) => s.pausedConversationId);
  const setPausedConversationId = useAppStore((s) => s.setPausedConversationId);

  const topics = useMemo(() => getTopics(), []);

  const handleTopicPress = useCallback(
    async (topicKey: TopicKey) => {
      if (loadingTopic) return;

      setLoadingTopic(topicKey);
      try {
        const result = await apiClient.post<CreateConversationResponse>(
          '/api/conversations',
          { topic: topicKey },
        );

        if (result.error) {
          Alert.alert(t('errors.genericError'), result.error.message);
          return;
        }

        if (result.data) {
          startConversation(topicKey, result.data.id);
          navigation.navigate('Talk', {
            topic: topicKey,
            conversationId: result.data.id,
          });
        }
      } catch {
        Alert.alert(t('errors.connectionTitle'), t('errors.connectionMessage'));
      } finally {
        setLoadingTopic(null);
      }
    },
    [loadingTopic, navigation, startConversation],
  );

  const handleResume = useCallback(async () => {
    if (!pausedConversationId || isResuming) return;

    setIsResuming(true);
    try {
      const result = await apiClient.post<CreateConversationResponse>(
        `/api/conversations/${pausedConversationId}/resume`,
      );

      if (result.error) {
        Alert.alert(t('errors.genericError'), result.error.message);
        return;
      }

      if (result.data) {
        const topic = (result.data.topic ?? 'sports') as TopicKey;
        startConversation(topic, pausedConversationId);
        setPausedConversationId(null);
        navigation.navigate('Talk', {
          topic,
          conversationId: pausedConversationId,
        });
      }
    } catch {
      Alert.alert(t('errors.connectionTitle'), t('errors.resumeError'));
    } finally {
      setIsResuming(false);
    }
  }, [pausedConversationId, isResuming, navigation, startConversation, setPausedConversationId]);

  const handleHistoryPress = useCallback(() => {
    navigation.navigate('HistoryList');
  }, [navigation]);

  const renderTopicCard = useCallback(
    ({ item }: { item: Topic }) => (
      <TopicCard
        topic={item}
        isLoading={loadingTopic === item.key}
        isDisabled={loadingTopic !== null}
        onPress={handleTopicPress}
      />
    ),
    [loadingTopic, handleTopicPress],
  );

  return (
    <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
      {/* Header area */}
      <View style={styles.header}>
        <View style={styles.headerRow}>
          <View style={styles.headerSpacer} />
          <LogoIcon />
          <Pressable
            onPress={handleHistoryPress}
            style={styles.historyButton}
            testID="history-button"
            accessibilityRole="button"
            accessibilityLabel={t('history.title')}
          >
            <HistoryIcon size={20} color={Colors.textPrimary} />
          </Pressable>
        </View>

        <Text style={styles.greeting} testID="home-greeting">{t('home.greeting')}</Text>
        <Text style={styles.subtitle}>{t('home.subtitle')}</Text>
      </View>

      {/* Paused conversation banner */}
      {pausedConversationId ? (
        <View style={styles.pausedWrapper}>
          <PausedConversationBanner
            onResume={handleResume}
            isResuming={isResuming}
          />
        </View>
      ) : null}

      {/* Topics section */}
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionLabel}>{t('home.topics')}</Text>
      </View>

      <FlatList
        data={topics}
        renderItem={renderTopicCard}
        keyExtractor={(item) => item.key}
        contentContainerStyle={styles.list}
        showsVerticalScrollIndicator={false}
      />
    </SafeAreaView>
  );
}

const ICON_CONTAINER_SIZE = 40;

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.surfacePrimary,
  },
  // Header
  header: {
    paddingHorizontal: 20,
    paddingTop: 8,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 20,
  },
  headerSpacer: {
    width: 40,
    height: 40,
  },
  historyButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: Colors.borderDefault,
    backgroundColor: Colors.surfaceCard,
    justifyContent: 'center',
    alignItems: 'center',
  },
  greeting: {
    ...Typography.title.ja,
    color: Colors.textPrimary,
    marginBottom: 8,
  },
  subtitle: {
    ...Typography.bodySmall.ja,
    color: Colors.textSecondary,
    marginBottom: 24,
  },
  // Paused conversation banner
  pausedWrapper: {
    paddingHorizontal: 20,
    marginBottom: 24,
  },
  pausedBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: Colors.surfaceCard,
    borderRadius: 14,
    paddingHorizontal: 17,
    paddingVertical: 15,
    borderWidth: 1,
    borderColor: Colors.borderDefault,
  },
  pausedLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  pausedPlayIcon: {
    width: 40,
    height: 40,
    borderRadius: 10,
    backgroundColor: Colors.surfaceElevated,
    justifyContent: 'center',
    alignItems: 'center',
  },
  pausedTitle: {
    ...Typography.bodyLarge.ja,
    color: Colors.textPrimary,
  },
  pausedTimestamp: {
    ...Typography.captionSmall.ja,
    color: Colors.textTertiary,
  },
  resumeButton: {
    minWidth: 44,
    minHeight: 44,
    justifyContent: 'center',
    alignItems: 'center',
  },
  resumeText: {
    ...Typography.body.ja,
    color: Colors.buttonGhostText,
  },
  // Section
  sectionHeader: {
    paddingHorizontal: 20,
    paddingBottom: 12,
  },
  sectionLabel: {
    ...Typography.captionSmall.en,
    color: Colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
  // Topic cards
  list: {
    paddingHorizontal: 20,
    paddingBottom: 20,
    gap: 8,
  },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: Colors.surfaceCard,
    borderRadius: 14,
    paddingHorizontal: 17,
    paddingVertical: 15,
    borderWidth: 1,
    borderColor: Colors.borderSubtle,
  },
  cardPressed: {
    opacity: 0.7,
    transform: [{ scale: 0.98 }],
  },
  cardDisabled: {
    opacity: 0.5,
  },
  cardContent: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
  },
  iconContainer: {
    width: ICON_CONTAINER_SIZE,
    height: ICON_CONTAINER_SIZE,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  topicLabel: {
    ...Typography.bodyLarge.ja,
    color: Colors.textPrimary,
  },
  cardRight: {
    width: 32,
    alignItems: 'center',
  },
  chevron: {
    ...Typography.body.en,
    color: Colors.chevron,
  },
});
