/**
 * i18n configuration using i18n-js + expo-localization.
 *
 * Language selection logic (from requirements doc section 4.1):
 * - Japanese OS → Japanese UI
 * - English OS → English UI
 * - Other language OS → English UI (fallback)
 */
import { I18n } from 'i18n-js';
import { getLocales } from 'expo-localization';
import en from './locales/en';
import ja from './locales/ja';

const i18n = new I18n({ en, ja });

// Determine default language from OS setting
const deviceLocales = getLocales();
const deviceLanguage = deviceLocales[0]?.languageCode ?? 'en';

// Japanese OS → ja, everything else → en (fallback)
i18n.locale = deviceLanguage === 'ja' ? 'ja' : 'en';
i18n.enableFallback = true;
i18n.defaultLocale = 'en';

export default i18n;

/**
 * Convenience function for translation.
 * Usage: t('home.greeting') or t('talk.completionText', { duration: '5分間' })
 */
export function t(scope: string, options?: Record<string, string | number>): string {
  return i18n.t(scope, options);
}

/**
 * Get the current locale code ('ja' or 'en').
 */
export function getCurrentLocale(): string {
  return i18n.locale;
}
