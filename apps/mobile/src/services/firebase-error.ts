/**
 * Maps Firebase Auth error codes to user-friendly i18n keys.
 */

import { t } from '@/i18n';

/** Firebase error code → i18n key mapping. */
const ERROR_MAP: Record<string, string> = {
  'auth/email-already-in-use': 'firebaseErrors.emailAlreadyInUse',
  'auth/invalid-email': 'firebaseErrors.invalidEmail',
  'auth/weak-password': 'firebaseErrors.weakPassword',
  'auth/user-not-found': 'firebaseErrors.invalidCredential',
  'auth/wrong-password': 'firebaseErrors.invalidCredential',
  'auth/invalid-credential': 'firebaseErrors.invalidCredential',
  'auth/too-many-requests': 'firebaseErrors.tooManyRequests',
  'auth/network-request-failed': 'firebaseErrors.networkError',
  'auth/user-disabled': 'firebaseErrors.userDisabled',
};

/** Error codes that indicate the user cancelled sign-in (not a real error). */
const CANCEL_CODES = new Set([
  'SIGN_IN_CANCELLED',       // @react-native-google-signin
  'ERR_REQUEST_CANCELED',    // @invertase/react-native-apple-authentication
  '1000',                    // Apple auth numeric cancel code
]);

/**
 * Returns true if the error represents a user-initiated cancellation
 * of a sign-in flow (Google or Apple).
 */
export function isSignInCancelled(error: unknown): boolean {
  if (typeof error === 'object' && error !== null && 'code' in error) {
    return CANCEL_CODES.has(String((error as { code: unknown }).code));
  }
  return false;
}

/**
 * Extract a user-friendly message from a Firebase Auth error.
 *
 * Firebase errors from `@react-native-firebase` have a `code` property
 * (e.g. `auth/email-already-in-use`). This function maps known codes
 * to translated messages and falls back to a generic message for unknown codes.
 */
export function getFirebaseErrorMessage(error: unknown, fallback: string): string {
  if (typeof error === 'object' && error !== null && 'code' in error) {
    const code = (error as { code: string }).code;
    const key = ERROR_MAP[code];
    if (key) {
      return t(key);
    }
  }
  return fallback;
}
