/**
 * Design system colors — Primitive + Semantic layers.
 *
 * Primitive: base palette matching Figma "Color Styles > Primitive".
 * Semantic: role-based tokens referencing Primitives.
 *
 * Rule: components use `Colors.*` (semantic), NOT `Primitive.*` directly,
 * except for rare one-off cases where no semantic token exists.
 */

// ---------------------------------------------------------------------------
// Primitive — raw palette values (not exported; use Semantic instead)
// ---------------------------------------------------------------------------

const Primitive = {
  primary: {
    500: '#3B82F6',
    400: '#60A5FA',
    300: '#93C5FD',
    200: '#BFDBFE',
    100: '#DBEAFE',
    50: '#EFF6FF',
  },
  neutral: {
    900: '#1E293B',
    800: '#334155',
    600: '#64748B',
    500: '#94A3B8',
    400: '#CBD5E1',
    300: '#E2E8F0',
    200: '#F0F4F8',
    50: '#FAFBFD',
  },
  status: {
    success: '#22C55E',
    warning: '#F59E0B',
    error: '#EF4444',
    successBg: '#F0FDF4',
    warningBg: '#FFFBEB',
    errorBg: '#FEF2F2',
  },
  white: '#FFFFFF',
} as const;

// ---------------------------------------------------------------------------
// Semantic — role-based tokens consumed by components
// ---------------------------------------------------------------------------

export const Colors = {
  // -- Surface --
  surfacePrimary: Primitive.neutral[50],     // #FAFBFD  main background
  surfaceCard: Primitive.white,               // #FFFFFF  card background
  surfaceElevated: Primitive.neutral[200],    // #F0F4F8  elevated / badge bg
  borderDefault: Primitive.neutral[300],      // #E2E8F0  default border
  borderSubtle: Primitive.neutral[200],       // #F0F4F8  card / subtle border

  // -- Text --
  textPrimary: Primitive.neutral[900],        // #1E293B
  textSecondary: Primitive.neutral[600],      // #64748B
  textTertiary: Primitive.neutral[500],       // #94A3B8
  textInverse: Primitive.white,               // #FFFFFF

  // -- Button --
  buttonPrimaryBg: Primitive.primary[500],    // #3B82F6
  buttonGhostText: Primitive.primary[500],    // #3B82F6
  buttonGhostBorder: Primitive.primary[200],  // #BFDBFE
  buttonDangerText: Primitive.status.error,   // #EF4444
  buttonDangerBg: Primitive.status.errorBg,   // #FEF2F2

  // -- Chat --
  chatAiBubbleBg: Primitive.white,            // #FFFFFF
  chatAiBubbleBorder: Primitive.neutral[200], // #F0F4F8

  // -- Correction --
  correctionHighlightText: '#166534',
  correctionHighlightBg: '#BBF7D0',

  // -- Topic --
  topicSports: '#2563EB',
  topicSportsBg: Primitive.primary[100],      // #DBEAFE
  topicBusiness: '#16A34A',
  topicBusinessBg: '#DCFCE7',
  topicPolitics: '#7C3AED',
  topicPoliticsBg: '#EDE9FE',
  topicTechnology: '#DC2626',
  topicTechnologyBg: '#FEE2E2',
  topicEntertainment: '#D97706',
  topicEntertainmentBg: '#FEF3C7',

  // -- Status (primitive passthrough for stat displays) --
  statusSuccess: Primitive.status.success,    // #22C55E
  statusWarning: Primitive.status.warning,    // #F59E0B
  statusError: Primitive.status.error,        // #EF4444
  statusSuccessBg: Primitive.status.successBg, // #F0FDF4
  statusWarningBg: Primitive.status.warningBg, // #FFFBEB
  statusErrorBg: Primitive.status.errorBg,    // #FEF2F2

  // -- Accent (primary-tinted surfaces) --
  accentBg: Primitive.primary[50],            // #EFF6FF  info cards, pressed states
  accentBorder: Primitive.primary[200],       // #BFDBFE  accent borders (cards, banners)
  accentMuted: Primitive.primary[400],        // #60A5FA  waveform bars, decorative

  // -- Misc (primitive passthrough) --
  chevron: Primitive.neutral[400],            // #CBD5E1
} as const;
