import { useState, useCallback, useRef } from 'react';
import {
  View,
  Text,
  Pressable,
  StyleSheet,
  Animated,
  Easing,
  type LayoutChangeEvent,
} from 'react-native';
import { Colors } from '@/constants/colors';
import { Typography } from '@/constants/typography';
import { t } from '@/i18n';
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  SpinnerIcon,
} from '@/components/icons';
import { computeWordDiff, splitTrailingPunct } from '@/utils/word-diff';
import type { TurnCorrection, CorrectionItem } from '@/types/conversation';

const ANIMATION_DURATION = 300;

interface CorrectionAnnotationProps {
  correctionStatus: 'none' | 'pending' | 'clean' | 'has_corrections';
  correction?: TurnCorrection;
}

/**
 * Inline correction annotation shown below user message bubbles.
 * Shows checking status, clean status, or expandable correction card.
 */
export function CorrectionAnnotation({
  correctionStatus,
  correction,
}: CorrectionAnnotationProps) {
  const [expanded, setExpanded] = useState(false);
  const [cardMounted, setCardMounted] = useState(false);
  const [contentHeight, setContentHeight] = useState(0);
  const animValue = useRef(new Animated.Value(0)).current;

  const handleToggle = useCallback(() => {
    const toExpanded = !expanded;
    setExpanded(toExpanded);
    if (toExpanded) {
      setCardMounted(true);
    }
    Animated.timing(animValue, {
      toValue: toExpanded ? 1 : 0,
      duration: ANIMATION_DURATION,
      easing: toExpanded
        ? Easing.out(Easing.cubic)
        : Easing.in(Easing.cubic),
      useNativeDriver: false,
    }).start(({ finished }) => {
      if (finished && !toExpanded) setCardMounted(false);
    });
  }, [expanded, animValue]);

  const handleContentLayout = useCallback((event: LayoutChangeEvent) => {
    const h = Math.ceil(event.nativeEvent.layout.height);
    if (h > 0) setContentHeight(h);
  }, []);

  if (correctionStatus === 'none') return null;

  if (correctionStatus === 'pending') {
    return (
      <View style={styles.checkingRow} testID="correction-checking">
        <SpinnerIcon size={12} color={Colors.buttonPrimaryBg} strokeWidth={2} />
        <Text style={styles.checkingText}>{t('corrections.checking')}</Text>
      </View>
    );
  }

  if (correctionStatus === 'clean') {
    return (
      <View style={styles.annotationRow} testID="correction-clean">
        <CheckCircleIcon size={16} color={Colors.statusSuccess} />
        <Text style={styles.annotationText}>{t('corrections.noCorrections')}</Text>
      </View>
    );
  }

  // has_corrections
  const itemCount = correction?.items.length ?? 0;
  const countLabel =
    itemCount === 1
      ? t('corrections.correctionCountOne')
      : t('corrections.correctionCount', { count: itemCount });

  return (
    <View style={styles.correctionWrapper}>
      <Pressable
        style={styles.annotationRow}
        onPress={handleToggle}
        testID="correction-toggle"
        accessibilityRole="button"
        accessibilityLabel={countLabel}
      >
        <ExclamationCircleIcon size={16} color={Colors.statusWarning} />
        <Text style={styles.annotationText}>{countLabel}</Text>
        {expanded ? (
          <ChevronDownIcon size={10} color={Colors.textSecondary} />
        ) : (
          <ChevronRightIcon size={10} color={Colors.textSecondary} />
        )}
      </Pressable>

      {cardMounted && correction ? (
        <Animated.View
          style={[
            contentHeight > 0
              ? [
                  styles.animatedContainer,
                  {
                    height: animValue.interpolate({
                      inputRange: [0, 1],
                      outputRange: [0, contentHeight],
                    }),
                    opacity: animValue,
                  },
                ]
              : styles.measureContainer,
          ]}
          pointerEvents={expanded ? 'auto' : 'none'}
        >
          <View onLayout={handleContentLayout}>
            <ExpandedCorrectionCard correction={correction} />
          </View>
        </Animated.View>
      ) : null}
    </View>
  );
}

interface ExpandedCorrectionCardProps {
  correction: TurnCorrection;
}

/**
 * Expanded correction card showing corrected text with inline highlights,
 * a divider, and the full explanation.
 */
function ExpandedCorrectionCard({ correction }: ExpandedCorrectionCardProps) {
  return (
    <View style={styles.expandedCard} testID="correction-card">
      {/* Corrected text with highlighted corrections */}
      <Text style={styles.correctedText} testID="correction-corrected-text">
        {renderCorrectedText(correction.correctedText, correction.items)}
      </Text>

      {/* Divider */}
      <View style={styles.cardDivider} />

      {/* Explanation */}
      <Text style={styles.explanationText} testID="correction-explanation">
        {correction.explanation}
      </Text>
    </View>
  );
}

/**
 * Render the full corrected text with only the diff words highlighted.
 * For each correction item, computes the word-level diff between
 * original and corrected phrases, then highlights only changed/added words.
 */
function renderCorrectedText(
  correctedText: string,
  items: CorrectionItem[],
): React.ReactNode[] {
  // Collect character ranges for diff-only highlights
  const highlights: { start: number; end: number }[] = [];

  for (const item of items) {
    const phraseStart = correctedText.indexOf(item.corrected);
    if (phraseStart === -1) continue;

    const { correctedSegments } = computeWordDiff(item.original, item.corrected);

    // Walk through segments sequentially to map character positions
    let charOffset = 0;
    for (const segment of correctedSegments) {
      const segIdx = item.corrected.indexOf(segment.text, charOffset);
      if (segIdx === -1) continue;

      if (segment.isDiff) {
        const [word] = splitTrailingPunct(segment.text);
        highlights.push({
          start: phraseStart + segIdx,
          end: phraseStart + segIdx + word.length,
        });
      }

      charOffset = segIdx + segment.text.length;
    }
  }

  // Sort by position
  highlights.sort((a, b) => a.start - b.start);

  // Merge overlapping highlights
  const merged: { start: number; end: number }[] = [];
  for (const h of highlights) {
    const last = merged[merged.length - 1];
    if (last && h.start <= last.end) {
      last.end = Math.max(last.end, h.end);
    } else {
      merged.push({ start: h.start, end: h.end });
    }
  }

  // Build text segments
  const parts: React.ReactNode[] = [];
  let pos = 0;

  for (let i = 0; i < merged.length; i++) {
    const h = merged[i];
    if (h.start > pos) {
      parts.push(correctedText.slice(pos, h.start));
    }
    parts.push(
      <Text key={`h${i}`} style={styles.correctedHighlight}>
        {correctedText.slice(h.start, h.end)}
      </Text>,
    );
    pos = h.end;
  }

  if (pos < correctedText.length) {
    parts.push(correctedText.slice(pos));
  }

  return parts;
}

const styles = StyleSheet.create({
  // -- Checking row (spinner + text, gap 8) --
  checkingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  checkingText: {
    ...Typography.caption.en,
    color: Colors.textTertiary,
  },
  // -- Wrapper for correction toggle + expanded card --
  correctionWrapper: {
    gap: 8,
  },
  // -- Annotation row (inline under bubble) --
  annotationRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
  },
  annotationText: {
    ...Typography.caption.en,
    color: Colors.textSecondary,
  },

  // -- Animated accordion container --
  animatedContainer: {
    overflow: 'hidden',
  },
  // -- Invisible container for measuring content height before first animation --
  measureContainer: {
    position: 'absolute',
    left: 0,
    right: 0,
    opacity: 0,
  },
  // -- Expanded correction card --
  expandedCard: {
    backgroundColor: Colors.statusWarningBg,
    borderWidth: 1,
    borderColor: Colors.statusWarning,
    borderRadius: 12,
    paddingTop: 13,
    paddingBottom: 15,
    paddingHorizontal: 15,
    gap: 10,
  },
  correctedText: {
    ...Typography.bodySmall.en,
    color: Colors.textPrimary,
  },
  correctedHighlight: {
    backgroundColor: Colors.correctionHighlightBg,
    color: Colors.correctionHighlightText,
  },
  cardDivider: {
    height: 1,
    backgroundColor: Colors.statusWarning,
  },
  explanationText: {
    ...Typography.bodySmall.ja,
    color: Colors.textSecondary,
  },
});
