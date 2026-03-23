import { getBadgeColor } from '../badge-colors';

describe('getBadgeColor', () => {
  it('returns an object with bg and text properties', () => {
    const result = getBadgeColor('sports');

    expect(result).toHaveProperty('bg');
    expect(result).toHaveProperty('text');
    expect(typeof result.bg).toBe('string');
    expect(typeof result.text).toBe('string');
  });

  it('returns the same color for the same keyword (deterministic)', () => {
    const first = getBadgeColor('technology');
    const second = getBadgeColor('technology');

    expect(first).toEqual(second);
  });

  it('returns valid hex color strings', () => {
    const hexRegex = /^#[0-9A-Fa-f]{6}$/;
    const result = getBadgeColor('business');

    expect(result.bg).toMatch(hexRegex);
    expect(result.text).toMatch(hexRegex);
  });

  it('can return different colors for different keywords', () => {
    const keywords = [
      'sports',
      'technology',
      'business',
      'politics',
      'entertainment',
      'science',
      'health',
      'education',
    ];
    const colors = keywords.map((kw) => getBadgeColor(kw));
    const uniqueBgs = new Set(colors.map((c) => c.bg));

    // With 8 keywords and 7 palette entries, we should get at least 2 distinct colors
    expect(uniqueBgs.size).toBeGreaterThanOrEqual(2);
  });

  it('handles empty string without crashing', () => {
    const result = getBadgeColor('');

    expect(result).toHaveProperty('bg');
    expect(result).toHaveProperty('text');
  });

  it('handles single character keyword', () => {
    const result = getBadgeColor('a');

    expect(result).toHaveProperty('bg');
    expect(result).toHaveProperty('text');
  });

  it('handles unicode characters', () => {
    const result = getBadgeColor('\u30B9\u30DD\u30FC\u30C4');

    expect(result).toHaveProperty('bg');
    expect(result).toHaveProperty('text');
  });

  it('handles emoji characters', () => {
    const result = getBadgeColor('\u{1F3C8}');

    expect(result).toHaveProperty('bg');
    expect(result).toHaveProperty('text');
  });

  it('handles long keyword strings', () => {
    const longKeyword = 'a'.repeat(10000);
    const result = getBadgeColor(longKeyword);

    expect(result).toHaveProperty('bg');
    expect(result).toHaveProperty('text');
  });
});
