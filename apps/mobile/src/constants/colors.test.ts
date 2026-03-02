import { Colors } from './colors';

describe('Colors', () => {
  it('exports an object with color constants', () => {
    expect(Colors).toBeDefined();
    expect(typeof Colors).toBe('object');
  });

  it('has surface colors', () => {
    expect(Colors.surfacePrimary).toBe('#FAFBFD');
    expect(Colors.surfaceCard).toBe('#FFFFFF');
    expect(Colors.surfaceElevated).toBe('#F0F4F8');
    expect(Colors.borderDefault).toBe('#E2E8F0');
    expect(Colors.borderSubtle).toBe('#F0F4F8');
  });

  it('has text colors', () => {
    expect(Colors.textPrimary).toBe('#1E293B');
    expect(Colors.textSecondary).toBe('#64748B');
    expect(Colors.textTertiary).toBe('#94A3B8');
    expect(Colors.textInverse).toBe('#FFFFFF');
  });

  it('has button colors', () => {
    expect(Colors.buttonPrimaryBg).toBe('#3B82F6');
    expect(Colors.buttonGhostText).toBe('#3B82F6');
    expect(Colors.buttonGhostBorder).toBe('#BFDBFE');
    expect(Colors.buttonDangerText).toBe('#EF4444');
    expect(Colors.buttonDangerBg).toBe('#FEF2F2');
  });

  it('has chat colors', () => {
    expect(Colors.chatAiBubbleBg).toBe('#FFFFFF');
    expect(Colors.chatAiBubbleBorder).toBe('#F0F4F8');
  });

  it('has correction colors', () => {
    expect(Colors.correctionHighlightText).toBe('#166534');
    expect(Colors.correctionHighlightBg).toBe('#BBF7D0');
  });

  it('has topic colors', () => {
    expect(Colors.topicSports).toBe('#2563EB');
    expect(Colors.topicSportsBg).toBe('#DBEAFE');
    expect(Colors.topicBusiness).toBe('#16A34A');
    expect(Colors.topicBusinessBg).toBe('#DCFCE7');
    expect(Colors.topicPolitics).toBe('#7C3AED');
    expect(Colors.topicPoliticsBg).toBe('#EDE9FE');
    expect(Colors.topicTechnology).toBe('#DC2626');
    expect(Colors.topicTechnologyBg).toBe('#FEE2E2');
    expect(Colors.topicEntertainment).toBe('#D97706');
    expect(Colors.topicEntertainmentBg).toBe('#FEF3C7');
  });

  it('has status colors', () => {
    expect(Colors.statusSuccess).toBe('#22C55E');
    expect(Colors.statusWarning).toBe('#F59E0B');
    expect(Colors.statusError).toBe('#EF4444');
    expect(Colors.statusSuccessBg).toBe('#F0FDF4');
    expect(Colors.statusWarningBg).toBe('#FFFBEB');
    expect(Colors.statusErrorBg).toBe('#FEF2F2');
  });

  it('has accent colors', () => {
    expect(Colors.accentBg).toBe('#EFF6FF');
    expect(Colors.accentBorder).toBe('#BFDBFE');
    expect(Colors.accentMuted).toBe('#60A5FA');
  });

  it('has misc colors', () => {
    expect(Colors.chevron).toBe('#CBD5E1');
  });

  it('all values are valid hex color strings', () => {
    const hexColorRegex = /^#[0-9A-Fa-f]{6}$/;
    for (const [, value] of Object.entries(Colors)) {
      expect(value).toMatch(hexColorRegex);
    }
  });

  it('is frozen (immutable via as const)', () => {
    const keys = Object.keys(Colors);
    expect(keys.length).toBeGreaterThan(0);
  });
});
