/**
 * Authentication state store.
 *
 * Manages Firebase auth state, sign-in/sign-out actions,
 * and email verification status.
 */

import { create } from 'zustand';

import type { FirebaseAuthTypes } from '@react-native-firebase/auth';

import { apiClient } from '@/api/client';
import {
  configureGoogleSignIn,
  getIdToken,
  onAuthStateChanged,
  reloadUser,
  sendEmailVerification as firebaseSendEmailVerification,
  sendPasswordResetEmail as firebaseSendPasswordResetEmail,
  signInWithApple,
  signInWithEmail,
  signInWithGoogle,
  signOut as firebaseSignOut,
  signUpWithEmail,
} from '@/services/firebase-auth';
import { t } from '@/i18n';
import { getFirebaseErrorMessage, isSignInCancelled } from '@/services/firebase-error';
import { registerTokenGetter } from '@/services/token-provider';
import { useSuggestionsStore } from '@/stores/suggestions-store';

interface AuthState {
  /** Firebase user object (null when signed out) */
  user: FirebaseAuthTypes.User | null;
  /** Whether the user is authenticated */
  isAuthenticated: boolean;
  /** Whether the user's email is verified (always true for Google/Apple SSO) */
  isEmailVerified: boolean;
  /** Loading state during auth operations */
  isLoading: boolean;
  /** Whether the initial auth state check is complete */
  isInitialized: boolean;
  /** Error message from the last auth operation */
  error: string | null;

  // Actions
  initialize: () => () => void;
  handleSignUpWithEmail: (email: string, password: string, displayName: string) => Promise<void>;
  handleSignInWithEmail: (email: string, password: string) => Promise<void>;
  handleSignInWithGoogle: () => Promise<void>;
  handleSignInWithApple: () => Promise<void>;
  handleSignOut: () => Promise<void>;
  resendVerification: () => Promise<void>;
  requestPasswordReset: (email: string) => Promise<void>;
  checkEmailVerified: () => Promise<boolean>;
  clearError: () => void;
  getToken: () => Promise<string | null>;
}

export const useAuthStore = create<AuthState>((set, _get) => ({
  user: null,
  isAuthenticated: false,
  isEmailVerified: false,
  isLoading: false,
  isInitialized: false,
  error: null,

  initialize: () => {
    configureGoogleSignIn();

    const unsubscribe = onAuthStateChanged(async (firebaseUser) => {
      if (firebaseUser) {
        set({
          user: firebaseUser,
          isAuthenticated: true,
          isEmailVerified: firebaseUser.emailVerified,
          isInitialized: true,
          isLoading: false,
        });
        // Fire both network calls in parallel — they are independent on
        // the backend. `/api/auth/session` creates/updates the user row,
        // and `/api/topics/suggestions` also goes through
        // `get_current_user` which calls `find_or_create_by_auth_uid`.
        // That helper is idempotent: concurrent INSERTs race on the
        // unique auth_uid, one side catches the IntegrityError and
        // re-reads the winning row, so both requests converge on the
        // same user. Parallelizing here saves ~800ms on first cold-start
        // launch — critical because the splash gate waits on the
        // suggestions prefetch.
        //
        // Neither call is awaited: session sync errors are non-critical
        // (get_current_user creates the row lazily), and the suggestions
        // prefetch has its own `isReady` signal the splash gate watches.
        apiClient.post('/api/auth/session').catch(() => {});
        useSuggestionsStore.getState().prefetch().catch(() => {});
      } else {
        set({
          user: null,
          isAuthenticated: false,
          isEmailVerified: false,
          isInitialized: true,
          isLoading: false,
        });
        useSuggestionsStore.getState().reset();
      }
    });

    return unsubscribe;
  },

  handleSignUpWithEmail: async (email, password, displayName) => {
    set({ isLoading: true, error: null });
    try {
      await signUpWithEmail(email, password, displayName);
      // onAuthStateChanged fires before updateProfile completes, so the
      // initial session sync may lack display_name. Re-sync now that the
      // profile and token are up to date.
      await apiClient.post('/api/auth/session').catch(() => {});
    } catch (err) {
      const message = getFirebaseErrorMessage(err, t('firebaseErrors.signUpFailed'));
      set({ isLoading: false, error: message });
      throw err;
    }
  },

  handleSignInWithEmail: async (email, password) => {
    set({ isLoading: true, error: null });
    try {
      await signInWithEmail(email, password);
    } catch (err) {
      const message = getFirebaseErrorMessage(err, t('firebaseErrors.signInFailed'));
      set({ isLoading: false, error: message });
      throw err;
    }
  },

  handleSignInWithGoogle: async () => {
    set({ isLoading: true, error: null });
    try {
      await signInWithGoogle();
    } catch (err) {
      if (isSignInCancelled(err)) {
        set({ isLoading: false });
        return;
      }
      const message = getFirebaseErrorMessage(err, t('firebaseErrors.signInFailed'));
      set({ isLoading: false, error: message });
      throw err;
    }
  },

  handleSignInWithApple: async () => {
    set({ isLoading: true, error: null });
    try {
      await signInWithApple();
    } catch (err) {
      if (isSignInCancelled(err)) {
        set({ isLoading: false });
        return;
      }
      const message = getFirebaseErrorMessage(err, t('firebaseErrors.signInFailed'));
      set({ isLoading: false, error: message });
      throw err;
    }
  },

  handleSignOut: async () => {
    set({ isLoading: true, error: null });
    try {
      await firebaseSignOut();
    } catch (err) {
      const message = getFirebaseErrorMessage(err, t('firebaseErrors.signOutFailed'));
      set({ isLoading: false, error: message });
      throw err;
    }
  },

  resendVerification: async () => {
    try {
      await firebaseSendEmailVerification();
    } catch (err) {
      const message = getFirebaseErrorMessage(err, t('firebaseErrors.resendFailed'));
      set({ error: message });
      throw err;
    }
  },

  requestPasswordReset: async (email) => {
    set({ isLoading: true, error: null });
    try {
      await firebaseSendPasswordResetEmail(email);
      set({ isLoading: false });
    } catch (err) {
      // Swallow `auth/user-not-found` to prevent account enumeration:
      // from the UI's perspective the request always succeeds, so an
      // attacker cannot infer whether an email is registered by comparing
      // error vs. success responses. Firebase itself does not send an
      // email to an unregistered address, so this is safe.
      const code = typeof err === 'object' && err !== null && 'code' in err
        ? String((err as { code: unknown }).code)
        : '';
      if (code === 'auth/user-not-found') {
        set({ isLoading: false });
        return;
      }
      const message = getFirebaseErrorMessage(err, t('firebaseErrors.passwordResetRequestFailed'));
      set({ isLoading: false, error: message });
      throw err;
    }
  },

  checkEmailVerified: async () => {
    const reloaded = await reloadUser();
    if (reloaded) {
      const verified = reloaded.emailVerified;
      set({ user: reloaded, isEmailVerified: verified });
      return verified;
    }
    return false;
  },

  clearError: () => set({ error: null }),

  getToken: () => getIdToken(),
}));

// Register the token getter so api/client can resolve tokens without
// importing auth-store (which would create a require cycle).
registerTokenGetter(() => getIdToken());
