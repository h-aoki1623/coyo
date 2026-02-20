import {
  formatDuration,
  formatTime,
  getSectionTitle,
  groupByDate,
  formatDetailHeader,
} from './format';

describe('formatDuration', () => {
  it('returns "--" for null seconds', () => {
    expect(formatDuration(null)).toBe('--');
  });

  it('returns "--" for zero seconds', () => {
    expect(formatDuration(0)).toBe('--');
  });

  it('returns "1\u5206\u672A\u6E80" for less than 60 seconds', () => {
    expect(formatDuration(1)).toBe('1\u5206\u672A\u6E80');
    expect(formatDuration(30)).toBe('1\u5206\u672A\u6E80');
    expect(formatDuration(59)).toBe('1\u5206\u672A\u6E80');
  });

  it('returns minutes for 60+ seconds', () => {
    expect(formatDuration(60)).toBe('1\u5206\u9593');
    expect(formatDuration(120)).toBe('2\u5206\u9593');
    expect(formatDuration(300)).toBe('5\u5206\u9593');
  });

  it('truncates partial minutes', () => {
    expect(formatDuration(90)).toBe('1\u5206\u9593');
    expect(formatDuration(179)).toBe('2\u5206\u9593');
  });

  it('handles large durations', () => {
    expect(formatDuration(3600)).toBe('60\u5206\u9593');
    expect(formatDuration(7200)).toBe('120\u5206\u9593');
  });
});

describe('formatTime', () => {
  it('formats a morning time in AM', () => {
    // 9:05 AM
    const result = formatTime('2026-01-15T09:05:00Z');
    // The exact output depends on the timezone the test runs in,
    // but it should match the pattern X:XX AM/PM
    expect(result).toMatch(/^\d{1,2}:\d{2} (AM|PM)$/);
  });

  it('formats noon as 12:XX PM', () => {
    const date = new Date(2026, 0, 15, 12, 0, 0);
    const result = formatTime(date.toISOString());
    expect(result).toBe('12:00 PM');
  });

  it('formats midnight as 12:XX AM', () => {
    const date = new Date(2026, 0, 15, 0, 0, 0);
    const result = formatTime(date.toISOString());
    expect(result).toBe('12:00 AM');
  });

  it('formats afternoon hours correctly', () => {
    const date = new Date(2026, 0, 15, 15, 30, 0);
    const result = formatTime(date.toISOString());
    expect(result).toBe('3:30 PM');
  });

  it('pads minutes with leading zero', () => {
    const date = new Date(2026, 0, 15, 8, 5, 0);
    const result = formatTime(date.toISOString());
    expect(result).toBe('8:05 AM');
  });

  it('handles 11 PM', () => {
    const date = new Date(2026, 0, 15, 23, 59, 0);
    const result = formatTime(date.toISOString());
    expect(result).toBe('11:59 PM');
  });
});

describe('getSectionTitle', () => {
  it('returns "\u4ECA\u65E5" for today', () => {
    const now = new Date(2026, 1, 20, 14, 0, 0);
    const todayISO = new Date(2026, 1, 20, 10, 0, 0).toISOString();

    expect(getSectionTitle(todayISO, now)).toBe('\u4ECA\u65E5');
  });

  it('returns "\u6628\u65E5" for yesterday', () => {
    const now = new Date(2026, 1, 20, 14, 0, 0);
    const yesterdayISO = new Date(2026, 1, 19, 10, 0, 0).toISOString();

    expect(getSectionTitle(yesterdayISO, now)).toBe('\u6628\u65E5');
  });

  it('returns formatted date for older dates', () => {
    const now = new Date(2026, 1, 20, 14, 0, 0);
    const olderISO = new Date(2026, 1, 15, 10, 0, 0).toISOString();

    expect(getSectionTitle(olderISO, now)).toBe('2\u670815\u65E5');
  });

  it('returns formatted date for a different month', () => {
    const now = new Date(2026, 1, 20, 14, 0, 0);
    const janISO = new Date(2026, 0, 5, 10, 0, 0).toISOString();

    expect(getSectionTitle(janISO, now)).toBe('1\u67085\u65E5');
  });

  it('handles dates two days ago (not yesterday)', () => {
    const now = new Date(2026, 1, 20, 14, 0, 0);
    const twoDaysAgoISO = new Date(2026, 1, 18, 10, 0, 0).toISOString();

    expect(getSectionTitle(twoDaysAgoISO, now)).toBe('2\u670818\u65E5');
  });
});

describe('groupByDate', () => {
  const now = new Date(2026, 1, 20, 14, 0, 0);

  it('returns empty array for empty input', () => {
    expect(groupByDate([], now)).toEqual([]);
  });

  it('groups items by date section', () => {
    const items = [
      { id: '1', startedAt: new Date(2026, 1, 20, 10, 0, 0).toISOString() },
      { id: '2', startedAt: new Date(2026, 1, 20, 11, 0, 0).toISOString() },
      { id: '3', startedAt: new Date(2026, 1, 19, 9, 0, 0).toISOString() },
    ];

    const sections = groupByDate(items, now);

    expect(sections).toHaveLength(2);
    expect(sections[0].title).toBe('\u4ECA\u65E5');
    expect(sections[0].data).toHaveLength(2);
    expect(sections[1].title).toBe('\u6628\u65E5');
    expect(sections[1].data).toHaveLength(1);
  });

  it('preserves item order within each section', () => {
    const items = [
      { id: '1', startedAt: new Date(2026, 1, 20, 10, 0, 0).toISOString() },
      { id: '2', startedAt: new Date(2026, 1, 20, 14, 0, 0).toISOString() },
    ];

    const sections = groupByDate(items, now);

    expect(sections[0].data[0].id).toBe('1');
    expect(sections[0].data[1].id).toBe('2');
  });

  it('preserves section order based on first occurrence', () => {
    const items = [
      { id: '1', startedAt: new Date(2026, 1, 19, 10, 0, 0).toISOString() },
      { id: '2', startedAt: new Date(2026, 1, 20, 10, 0, 0).toISOString() },
      { id: '3', startedAt: new Date(2026, 1, 15, 10, 0, 0).toISOString() },
    ];

    const sections = groupByDate(items, now);

    expect(sections).toHaveLength(3);
    expect(sections[0].title).toBe('\u6628\u65E5');
    expect(sections[1].title).toBe('\u4ECA\u65E5');
    expect(sections[2].title).toBe('2\u670815\u65E5');
  });

  it('handles a single item', () => {
    const items = [
      { id: '1', startedAt: new Date(2026, 1, 20, 10, 0, 0).toISOString() },
    ];

    const sections = groupByDate(items, now);

    expect(sections).toHaveLength(1);
    expect(sections[0].data).toHaveLength(1);
  });
});

describe('formatDetailHeader', () => {
  const now = new Date(2026, 1, 20, 14, 0, 0);

  it('formats today with time and duration', () => {
    const todayAt10 = new Date(2026, 1, 20, 10, 30, 0);
    const result = formatDetailHeader(todayAt10.toISOString(), 300, now);

    expect(result).toBe('\u4ECA\u65E5 10:30 AM \u00B7 5\u5206\u9593');
  });

  it('formats yesterday with time and duration', () => {
    const yesterdayAt15 = new Date(2026, 1, 19, 15, 0, 0);
    const result = formatDetailHeader(yesterdayAt15.toISOString(), 120, now);

    expect(result).toBe('\u6628\u65E5 3:00 PM \u00B7 2\u5206\u9593');
  });

  it('formats older date with time and duration', () => {
    const older = new Date(2026, 1, 10, 9, 5, 0);
    const result = formatDetailHeader(older.toISOString(), 600, now);

    expect(result).toBe('2\u670810\u65E5 9:05 AM \u00B7 10\u5206\u9593');
  });

  it('formats with null duration', () => {
    const todayAt10 = new Date(2026, 1, 20, 10, 0, 0);
    const result = formatDetailHeader(todayAt10.toISOString(), null, now);

    expect(result).toContain('--');
  });

  it('formats with zero duration', () => {
    const todayAt10 = new Date(2026, 1, 20, 10, 0, 0);
    const result = formatDetailHeader(todayAt10.toISOString(), 0, now);

    expect(result).toContain('--');
  });

  it('formats with short duration (less than 1 minute)', () => {
    const todayAt10 = new Date(2026, 1, 20, 10, 0, 0);
    const result = formatDetailHeader(todayAt10.toISOString(), 45, now);

    expect(result).toContain('1\u5206\u672A\u6E80');
  });
});
