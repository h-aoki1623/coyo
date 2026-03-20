import { memo } from 'react';
import { View, Text, Pressable, ActivityIndicator, StyleSheet } from 'react-native';

import { Colors } from '@/constants/colors';
import { Typography } from '@/constants/typography';
import { getBadgeColor } from '@/constants/badge-colors';
import { SpeechBubbleIcon } from '@/components/icons';
import type { TopicSuggestion } from '@/types/suggestion';

interface Props {
  suggestion: TopicSuggestion;
  onPress: (suggestion: TopicSuggestion) => void;
  isLoading: boolean;
  isDisabled: boolean;
}

export const SuggestionCard = memo(function SuggestionCard({
  suggestion,
  onPress,
  isLoading,
  isDisabled,
}: Props) {
  const badgeColor = getBadgeColor(suggestion.sourceKeyword);

  return (
    <Pressable
      style={({ pressed }) => [
        styles.card,
        pressed && styles.cardPressed,
        isDisabled && !isLoading && styles.cardDisabled,
      ]}
      onPress={() => onPress(suggestion)}
      disabled={isDisabled}
      testID={`suggestion-${suggestion.id}`}
      accessibilityRole="button"
      accessibilityLabel={suggestion.title}
    >
      <View style={[styles.iconContainer, { backgroundColor: badgeColor.bg }]}>
        <SpeechBubbleIcon size={22} color={badgeColor.text} />
      </View>
      <View style={styles.content}>
        <Text style={styles.title} numberOfLines={1}>{suggestion.title}</Text>
        <Text style={styles.summary} numberOfLines={2}>{suggestion.summary}</Text>
        <View style={styles.badgeRow}>
          {isLoading ? (
            <ActivityIndicator size="small" color={Colors.buttonPrimaryBg} />
          ) : (
            <View style={[styles.badge, { backgroundColor: badgeColor.bg }]}>
              <Text style={[styles.badgeText, { color: badgeColor.text }]}>
                {suggestion.sourceKeyword}
              </Text>
            </View>
          )}
        </View>
      </View>
    </Pressable>
  );
});

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    backgroundColor: Colors.surfaceCard,
    borderRadius: 14,
    paddingHorizontal: 17,
    paddingVertical: 15,
    borderWidth: 1,
    borderColor: Colors.borderSubtle,
    gap: 12,
  },
  cardPressed: {
    opacity: 0.7,
    transform: [{ scale: 0.98 }],
  },
  cardDisabled: {
    opacity: 0.5,
  },
  iconContainer: {
    width: 40,
    height: 40,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  content: {
    flex: 1,
    gap: 4,
  },
  title: {
    ...Typography.bodyLarge.en,
    color: Colors.textPrimary,
  },
  summary: {
    ...Typography.caption.en,
    color: Colors.textTertiary,
  },
  badgeRow: {
    flexDirection: 'row',
    marginTop: 4,
  },
  badge: {
    borderRadius: 100,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  badgeText: {
    ...Typography.captionSmall.en,
  },
});
