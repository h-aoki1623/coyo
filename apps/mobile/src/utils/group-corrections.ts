import type {
  TurnCorrection,
  SentenceCorrection,
} from '@/types/conversation';

/**
 * Group correction items by sentence across all turns.
 *
 * Items that share the same `originalSentence` within the same
 * TurnCorrection are merged into a single `SentenceCorrection`.
 * The output preserves insertion order (first occurrence wins).
 *
 * Pure function — does not mutate its input.
 */
export function groupCorrectionsBySentence(
  corrections: readonly TurnCorrection[],
): SentenceCorrection[] {
  const map = new Map<string, SentenceCorrection>();

  for (const turn of corrections) {
    for (const item of turn.items) {
      const key = `${turn.id}::${item.originalSentence}`;
      const existing = map.get(key);

      if (existing) {
        // Append item — create a new object to avoid mutation
        map.set(key, {
          ...existing,
          items: [...existing.items, item],
        });
      } else {
        map.set(key, {
          key,
          originalSentence: item.originalSentence,
          correctedSentence: item.correctedSentence,
          items: [item],
        });
      }
    }
  }

  return Array.from(map.values());
}
