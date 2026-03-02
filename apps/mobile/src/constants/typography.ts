/**
 * Typography constants matching the Figma design system.
 * Uses Noto Sans JP for Japanese text and Plus Jakarta Sans for Latin text.
 *
 * Typography presets map each design role to a TextStyle with fontFamily,
 * fontSize, and lineHeight. Use `.en` for English/Latin text and `.ja`
 * for Japanese text.
 *
 * Usage:
 *   import { Typography } from '@/constants/typography';
 *   const styles = StyleSheet.create({
 *     greeting: { ...Typography.title.ja, color: Colors.textPrimary },
 *   });
 */
import type { TextStyle } from 'react-native';

export const Fonts = {
  notoSansJP: {
    regular: 'NotoSansJP_400Regular',
    medium: 'NotoSansJP_500Medium',
    bold: 'NotoSansJP_700Bold',
  },
  plusJakartaSans: {
    regular: 'PlusJakartaSans_400Regular',
    medium: 'PlusJakartaSans_500Medium',
    semiBold: 'PlusJakartaSans_600SemiBold',
    bold: 'PlusJakartaSans_700Bold',
  },
} as const;

interface TypographyVariant {
  readonly en: TextStyle;
  readonly ja: TextStyle;
}

/**
 * Design system typography presets from Figma.
 * Each role provides `.en` and `.ja` variants with the correct font family,
 * size, and line height. Spread into StyleSheet styles:
 *
 *   heading: { ...Typography.title.ja, color: Colors.textPrimary }
 */
export const Typography: Record<string, TypographyVariant> = {
  /** 28px Bold — Statistics numbers (turns, corrections) */
  display: {
    en: { fontFamily: Fonts.plusJakartaSans.bold, fontSize: 28 },
    ja: { fontFamily: Fonts.notoSansJP.bold, fontSize: 28 },
  },
  /** 20px Bold — Navigation bar screen titles */
  title: {
    en: { fontFamily: Fonts.plusJakartaSans.bold, fontSize: 20 },
    ja: { fontFamily: Fonts.notoSansJP.bold, fontSize: 20 },
  },
  /** 18px Bold — Section headings, offline title */
  headline: {
    en: { fontFamily: Fonts.plusJakartaSans.bold, fontSize: 18 },
    ja: { fontFamily: Fonts.notoSansJP.bold, fontSize: 18 },
  },
  /** 17px SemiBold(EN)/Bold(JA) — Topic names, persona name, emphasis */
  bodyLarge: {
    en: { fontFamily: Fonts.plusJakartaSans.semiBold, fontSize: 17 },
    ja: { fontFamily: Fonts.notoSansJP.bold, fontSize: 17 },
  },
  /** 16px Regular, lineHeight 160% — Chat bubbles, buttons, body text */
  body: {
    en: { fontFamily: Fonts.plusJakartaSans.regular, fontSize: 16, lineHeight: 25.6 },
    ja: { fontFamily: Fonts.notoSansJP.regular, fontSize: 16, lineHeight: 25.6 },
  },
  /** 15px Regular, lineHeight 160% — Record prompt, auxiliary buttons, subtitles */
  bodySmall: {
    en: { fontFamily: Fonts.plusJakartaSans.regular, fontSize: 15, lineHeight: 24 },
    ja: { fontFamily: Fonts.notoSansJP.regular, fontSize: 15, lineHeight: 24 },
  },
  /** 13px Regular, lineHeight 160% — Explanations, subtext, stat labels */
  caption: {
    en: { fontFamily: Fonts.plusJakartaSans.regular, fontSize: 13, lineHeight: 20.8 },
    ja: { fontFamily: Fonts.notoSansJP.regular, fontSize: 13, lineHeight: 20.8 },
  },
  /** 12px SemiBold(EN)/Medium(JA) — Dates, badges, section labels */
  captionSmall: {
    en: { fontFamily: Fonts.plusJakartaSans.semiBold, fontSize: 12 },
    ja: { fontFamily: Fonts.notoSansJP.medium, fontSize: 12 },
  },
} as const;
