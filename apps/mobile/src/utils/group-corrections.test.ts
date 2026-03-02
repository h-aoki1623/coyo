import { groupCorrectionsBySentence } from './group-corrections';
import type { TurnCorrection, CorrectionItem } from '@/types/conversation';

function makeItem(overrides: Partial<CorrectionItem> = {}): CorrectionItem {
  return {
    id: 'item-1',
    original: 'go',
    corrected: 'went',
    originalSentence: 'I go to school yesterday.',
    correctedSentence: 'I went to school yesterday.',
    type: 'grammar',
    explanation: 'Past tense required.',
    ...overrides,
  };
}

function makeTurn(
  overrides: Partial<TurnCorrection> & { items: CorrectionItem[] },
): TurnCorrection {
  return {
    id: 'turn-1',
    turnId: 'tid-1',
    correctedText: '',
    explanation: '',
    ...overrides,
  };
}

describe('groupCorrectionsBySentence', () => {
  it('returns empty array for empty input', () => {
    expect(groupCorrectionsBySentence([])).toEqual([]);
  });

  it('groups a single item into one SentenceCorrection', () => {
    const item = makeItem();
    const turn = makeTurn({ items: [item] });

    const result = groupCorrectionsBySentence([turn]);

    expect(result).toHaveLength(1);
    expect(result[0]).toEqual({
      key: 'turn-1::I go to school yesterday.',
      originalSentence: 'I go to school yesterday.',
      correctedSentence: 'I went to school yesterday.',
      items: [item],
    });
  });

  it('merges multiple items from the same sentence into one group', () => {
    const item1 = makeItem({
      id: 'item-1',
      original: 'go',
      corrected: 'went',
      explanation: 'Past tense required.',
    });
    const item2 = makeItem({
      id: 'item-2',
      original: 'school',
      corrected: 'the school',
      explanation: 'Article needed.',
    });
    const turn = makeTurn({ items: [item1, item2] });

    const result = groupCorrectionsBySentence([turn]);

    expect(result).toHaveLength(1);
    expect(result[0].items).toHaveLength(2);
    expect(result[0].items[0]).toBe(item1);
    expect(result[0].items[1]).toBe(item2);
  });

  it('separates items from different sentences into different groups', () => {
    const item1 = makeItem({
      id: 'item-1',
      originalSentence: 'I go to school.',
      correctedSentence: 'I went to school.',
    });
    const item2 = makeItem({
      id: 'item-2',
      originalSentence: 'She have a cat.',
      correctedSentence: 'She has a cat.',
      original: 'have',
      corrected: 'has',
    });
    const turn = makeTurn({ items: [item1, item2] });

    const result = groupCorrectionsBySentence([turn]);

    expect(result).toHaveLength(2);
    expect(result[0].originalSentence).toBe('I go to school.');
    expect(result[1].originalSentence).toBe('She have a cat.');
  });

  it('keeps items from different turns separate even if same sentence', () => {
    const item = makeItem();
    const turn1 = makeTurn({ id: 'turn-1', items: [item] });
    const turn2 = makeTurn({ id: 'turn-2', items: [item] });

    const result = groupCorrectionsBySentence([turn1, turn2]);

    expect(result).toHaveLength(2);
    expect(result[0].key).toBe('turn-1::I go to school yesterday.');
    expect(result[1].key).toBe('turn-2::I go to school yesterday.');
  });

  it('preserves insertion order across multiple turns', () => {
    const itemA = makeItem({
      id: 'a',
      originalSentence: 'Sentence A.',
      correctedSentence: 'Sentence A fixed.',
    });
    const itemB = makeItem({
      id: 'b',
      originalSentence: 'Sentence B.',
      correctedSentence: 'Sentence B fixed.',
    });
    const itemC = makeItem({
      id: 'c',
      originalSentence: 'Sentence C.',
      correctedSentence: 'Sentence C fixed.',
    });
    const turn1 = makeTurn({ id: 'turn-1', items: [itemA, itemB] });
    const turn2 = makeTurn({ id: 'turn-2', items: [itemC] });

    const result = groupCorrectionsBySentence([turn1, turn2]);

    expect(result).toHaveLength(3);
    expect(result[0].originalSentence).toBe('Sentence A.');
    expect(result[1].originalSentence).toBe('Sentence B.');
    expect(result[2].originalSentence).toBe('Sentence C.');
  });

  it('does not mutate input corrections', () => {
    const item = makeItem();
    const turn = makeTurn({ items: [item] });
    const original = JSON.parse(JSON.stringify([turn]));

    groupCorrectionsBySentence([turn]);

    expect(JSON.stringify([turn])).toBe(JSON.stringify(original));
  });
});
