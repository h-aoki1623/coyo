import { findTopic, TOPICS } from './topics';

describe('TOPICS', () => {
  it('contains exactly 5 topics', () => {
    expect(TOPICS).toHaveLength(5);
  });

  it('has all expected topic keys', () => {
    const keys = TOPICS.map((t) => t.key);
    expect(keys).toEqual([
      'sports',
      'business',
      'politics',
      'technology',
      'entertainment',
    ]);
  });

  it('each topic has required fields', () => {
    for (const topic of TOPICS) {
      expect(topic).toHaveProperty('key');
      expect(topic).toHaveProperty('label');
      expect(topic).toHaveProperty('emoji');
      expect(topic).toHaveProperty('iconBg');
      expect(topic).toHaveProperty('iconColor');
      expect(typeof topic.key).toBe('string');
      expect(typeof topic.label).toBe('string');
      expect(typeof topic.emoji).toBe('string');
      expect(typeof topic.iconBg).toBe('string');
      expect(typeof topic.iconColor).toBe('string');
    }
  });

  it('all iconBg values are valid hex colors', () => {
    const hexColorRegex = /^#[0-9A-Fa-f]{6}$/;
    for (const topic of TOPICS) {
      expect(topic.iconBg).toMatch(hexColorRegex);
      expect(topic.iconColor).toMatch(hexColorRegex);
    }
  });
});

describe('findTopic', () => {
  it('returns the topic for a valid key', () => {
    const result = findTopic('sports');
    expect(result).toBeDefined();
    expect(result?.key).toBe('sports');
    expect(result?.label).toBe('\u30B9\u30DD\u30FC\u30C4');
  });

  it('returns the correct topic for each valid key', () => {
    expect(findTopic('business')?.key).toBe('business');
    expect(findTopic('politics')?.key).toBe('politics');
    expect(findTopic('technology')?.key).toBe('technology');
    expect(findTopic('entertainment')?.key).toBe('entertainment');
  });

  it('returns undefined for an unknown key', () => {
    const result = findTopic('cooking');
    expect(result).toBeUndefined();
  });

  it('returns undefined for an empty string', () => {
    const result = findTopic('');
    expect(result).toBeUndefined();
  });

  it('is case-sensitive', () => {
    expect(findTopic('Sports')).toBeUndefined();
    expect(findTopic('SPORTS')).toBeUndefined();
  });

  it('returns undefined for special characters', () => {
    expect(findTopic('sports!')).toBeUndefined();
    expect(findTopic(' sports')).toBeUndefined();
  });
});
