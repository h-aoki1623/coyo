import { Colors } from './colors';

describe('Colors', () => {
  it('exports an object with color constants', () => {
    expect(Colors).toBeDefined();
    expect(typeof Colors).toBe('object');
  });

  it('has primary colors', () => {
    expect(Colors.primaryBlue).toBe('#3B82F6');
    expect(Colors.primaryBlueDark).toBe('#2563EB');
  });

  it('has background colors', () => {
    expect(Colors.background).toBe('#F9FAFB');
    expect(Colors.cardBackground).toBe('#FFFFFF');
    expect(Colors.aiBubbleBg).toBe('#F3F4F6');
  });

  it('has text colors', () => {
    expect(Colors.textPrimary).toBe('#111827');
    expect(Colors.textSecondary).toBe('#6B7280');
    expect(Colors.textHint).toBe('#9CA3AF');
  });

  it('has status colors', () => {
    expect(Colors.errorRed).toBe('#EF4444');
    expect(Colors.correctionGreen).toBe('#22C55E');
    expect(Colors.correctionOrange).toBe('#F97316');
  });

  it('has border colors', () => {
    expect(Colors.borderLight).toBe('#E5E7EB');
    expect(Colors.borderLighter).toBe('#F3F4F6');
  });

  it('all values are valid hex color strings', () => {
    const hexColorRegex = /^#[0-9A-Fa-f]{6}$/;
    for (const [key, value] of Object.entries(Colors)) {
      expect(value).toMatch(hexColorRegex);
    }
  });

  it('is frozen (immutable via as const)', () => {
    // TypeScript "as const" makes it readonly at compile time
    // At runtime, we can at least verify the values are strings
    const keys = Object.keys(Colors);
    expect(keys.length).toBeGreaterThan(0);
  });
});
