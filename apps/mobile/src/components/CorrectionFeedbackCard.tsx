import React, { memo } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { HintCircleIcon } from '@/components/icons';
import { Colors } from '@/constants/colors';
import { Typography } from '@/constants/typography';
import { computeWordDiff, splitTrailingPunct } from '@/utils/word-diff';
import type { SentenceCorrection, CorrectionItem } from '@/types/conversation';

interface Props {
  sentenceCorrection: SentenceCorrection;
}

export const CorrectionFeedbackCard = memo(function CorrectionFeedbackCard({
  sentenceCorrection,
}: Props) {
  const { originalSentence, correctedSentence, items } = sentenceCorrection;

  return (
    <View style={styles.card}>
      {/* Original sentence — grey strikethrough, error words in red (no strikethrough) */}
      <Text style={styles.originalSentence}>
        {renderSentenceWithDiffs(originalSentence, items, 'original')}
      </Text>

      {/* Corrected sentence — normal text, corrected words with green highlight */}
      <Text style={styles.correctedSentence}>
        {renderSentenceWithDiffs(correctedSentence, items, 'corrected')}
      </Text>

      {/* Divider + explanations (one row per item) */}
      <View style={styles.explanationSection}>
        {items.map((item) => (
          <View key={item.id} style={styles.explanationRow}>
            <View style={styles.hintIconContainer}>
              <HintCircleIcon size={12} color={Colors.buttonPrimaryBg} />
            </View>
            <Text style={styles.explanationText}>{item.explanation}</Text>
          </View>
        ))}
      </View>
    </View>
  );
});

// -- Rendering helpers --

interface CharRange {
  start: number;
  end: number;
}

/**
 * Render a sentence with word-level diff highlights for multiple correction items.
 *
 * For each item the diff phrase is located in the sentence, word-level diff is
 * computed, and only truly changed words are highlighted. Ranges are merged so
 * overlapping corrections don't produce nested highlights.
 */
function renderSentenceWithDiffs(
  sentence: string,
  items: readonly CorrectionItem[],
  type: 'original' | 'corrected',
): React.ReactNode[] {
  const highlights = collectHighlightRanges(sentence, items, type);

  if (highlights.length === 0) {
    return [sentence];
  }

  const highlightStyle =
    type === 'original' ? styles.errorHighlight : styles.greenHighlight;

  const parts: React.ReactNode[] = [];
  let pos = 0;

  for (let i = 0; i < highlights.length; i++) {
    const h = highlights[i];
    if (h.start > pos) {
      parts.push(sentence.slice(pos, h.start));
    }
    parts.push(
      <Text key={`h${i}`} style={highlightStyle}>
        {sentence.slice(h.start, h.end)}
      </Text>,
    );
    pos = h.end;
  }

  if (pos < sentence.length) {
    parts.push(sentence.slice(pos));
  }

  return parts;
}

/**
 * Collect character-level highlight ranges from all items, sorted and merged.
 */
function collectHighlightRanges(
  sentence: string,
  items: readonly CorrectionItem[],
  type: 'original' | 'corrected',
): CharRange[] {
  const ranges: CharRange[] = [];

  for (const item of items) {
    const phrase = type === 'original' ? item.original : item.corrected;
    const phraseStart = sentence.indexOf(phrase);
    if (phraseStart === -1) continue;

    const { originalSegments, correctedSegments } = computeWordDiff(
      item.original,
      item.corrected,
    );
    const segments =
      type === 'original' ? originalSegments : correctedSegments;

    let charOffset = 0;
    for (const segment of segments) {
      const segIdx = phrase.indexOf(segment.text, charOffset);
      if (segIdx === -1) continue;

      if (segment.isDiff) {
        const [word] = splitTrailingPunct(segment.text);
        ranges.push({
          start: phraseStart + segIdx,
          end: phraseStart + segIdx + word.length,
        });
      }

      charOffset = segIdx + segment.text.length;
    }
  }

  // Sort by position
  ranges.sort((a, b) => a.start - b.start);

  // Merge overlapping ranges
  const merged: CharRange[] = [];
  for (const r of ranges) {
    const last = merged[merged.length - 1];
    if (last && r.start <= last.end) {
      last.end = Math.max(last.end, r.end);
    } else {
      merged.push({ start: r.start, end: r.end });
    }
  }

  return merged;
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Colors.surfaceCard,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: Colors.borderSubtle,
    padding: 17,
    gap: 8,
  },
  originalSentence: {
    ...Typography.bodySmall.en,
    color: Colors.textSecondary,
    textDecorationLine: 'line-through',
  },
  correctedSentence: {
    ...Typography.bodySmall.en,
    color: Colors.textPrimary,
  },
  errorHighlight: {
    color: Colors.statusError,
    textDecorationLine: 'none',
  },
  greenHighlight: {
    backgroundColor: Colors.correctionHighlightBg,
    color: Colors.correctionHighlightText,
    borderRadius: 4,
    paddingHorizontal: 4,
  },
  explanationSection: {
    borderTopWidth: 1,
    borderTopColor: Colors.borderSubtle,
  },
  explanationRow: {
    flexDirection: 'row',
    gap: 8,
    alignItems: 'flex-start',
    paddingTop: 13,
  },
  hintIconContainer: {
    width: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: Colors.surfaceElevated,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 2,
  },
  explanationText: {
    ...Typography.bodySmall.ja,
    color: Colors.textTertiary,
    flex: 1,
  },
});
