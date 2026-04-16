/**
 * Shared validation helpers for auth forms (sign-up, sign-in, password reset).
 */

import { t } from '@/i18n';

/** Minimum password length — matches firebaseErrors.weakPassword messaging. */
export const MIN_PASSWORD_LENGTH = 8;

/**
 * Upper cap to defend against resource exhaustion from megabyte-length inputs
 * reaching `confirmPasswordReset`. Firebase itself accepts up to 4096 chars,
 * but nothing legitimate needs that much.
 */
export const MAX_PASSWORD_LENGTH = 128;

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * Validate a password and return an i18n error message, or null if valid.
 */
export function validatePassword(password: string): string | null {
  if (password.length < MIN_PASSWORD_LENGTH) {
    return t('firebaseErrors.weakPassword');
  }
  if (password.length > MAX_PASSWORD_LENGTH) {
    return t('firebaseErrors.passwordTooLong');
  }
  return null;
}

/** Basic client-side email shape check. */
export function isEmailValid(email: string): boolean {
  return EMAIL_REGEX.test(email.trim());
}
