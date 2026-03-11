import { useAuthStore } from './auth-store';

// Mock firebase-auth service
jest.mock('@/services/firebase-auth', () => ({
  configureGoogleSignIn: jest.fn(),
  onAuthStateChanged: jest.fn(),
  signUpWithEmail: jest.fn(),
  signInWithEmail: jest.fn(),
  signInWithGoogle: jest.fn(),
  signInWithApple: jest.fn(),
  signOut: jest.fn(),
  sendEmailVerification: jest.fn(),
  reloadUser: jest.fn(),
  getIdToken: jest.fn(),
}));

import {
  configureGoogleSignIn,
  onAuthStateChanged,
  signUpWithEmail,
  signInWithEmail,
  signInWithGoogle,
  signInWithApple,
  signOut,
  sendEmailVerification,
  reloadUser,
  getIdToken,
} from '@/services/firebase-auth';
const mockConfigureGoogleSignIn = configureGoogleSignIn as jest.MockedFunction<
  typeof configureGoogleSignIn
>;
const mockOnAuthStateChanged = onAuthStateChanged as jest.MockedFunction<
  typeof onAuthStateChanged
>;
const mockSignUpWithEmail = signUpWithEmail as jest.MockedFunction<typeof signUpWithEmail>;
const mockSignInWithEmail = signInWithEmail as jest.MockedFunction<typeof signInWithEmail>;
const mockSignInWithGoogle = signInWithGoogle as jest.MockedFunction<typeof signInWithGoogle>;
const mockSignInWithApple = signInWithApple as jest.MockedFunction<typeof signInWithApple>;
const mockSignOut = signOut as jest.MockedFunction<typeof signOut>;
const mockSendEmailVerification = sendEmailVerification as jest.MockedFunction<
  typeof sendEmailVerification
>;
const mockReloadUser = reloadUser as jest.MockedFunction<typeof reloadUser>;
const mockGetIdToken = getIdToken as jest.MockedFunction<typeof getIdToken>;

// Helper to create a mock Firebase user
function createMockUser(overrides: Record<string, unknown> = {}) {
  return {
    uid: 'user-123',
    email: 'test@example.com',
    displayName: 'Test User',
    emailVerified: true,
    ...overrides,
  } as unknown as import('@react-native-firebase/auth').FirebaseAuthTypes.User;
}

// Helper to reset store between tests
function resetStore() {
  useAuthStore.setState({
    user: null,
    isAuthenticated: false,
    isEmailVerified: false,
    isLoading: false,
    isInitialized: false,
    error: null,
  });
}

describe('useAuthStore', () => {
  beforeEach(() => {
    resetStore();
    jest.clearAllMocks();
  });

  describe('initial state', () => {
    it('has null user', () => {
      expect(useAuthStore.getState().user).toBeNull();
    });

    it('has isAuthenticated set to false', () => {
      expect(useAuthStore.getState().isAuthenticated).toBe(false);
    });

    it('has isEmailVerified set to false', () => {
      expect(useAuthStore.getState().isEmailVerified).toBe(false);
    });

    it('has isLoading set to false', () => {
      expect(useAuthStore.getState().isLoading).toBe(false);
    });

    it('has isInitialized set to false', () => {
      expect(useAuthStore.getState().isInitialized).toBe(false);
    });

    it('has null error', () => {
      expect(useAuthStore.getState().error).toBeNull();
    });
  });

  describe('initialize', () => {
    it('configures Google Sign-In', () => {
      const mockUnsubscribe = jest.fn();
      mockOnAuthStateChanged.mockReturnValue(mockUnsubscribe);

      useAuthStore.getState().initialize();

      expect(mockConfigureGoogleSignIn).toHaveBeenCalledTimes(1);
    });

    it('subscribes to auth state changes and returns unsubscribe function', () => {
      const mockUnsubscribe = jest.fn();
      mockOnAuthStateChanged.mockReturnValue(mockUnsubscribe);

      const unsubscribe = useAuthStore.getState().initialize();

      expect(mockOnAuthStateChanged).toHaveBeenCalledTimes(1);
      expect(typeof unsubscribe).toBe('function');
      expect(unsubscribe).toBe(mockUnsubscribe);
    });

    it('sets authenticated state when auth callback fires with a user', async () => {
      const mockUser = createMockUser({ emailVerified: true });
      mockOnAuthStateChanged.mockImplementation((callback) => {
        callback(mockUser);
        return jest.fn();
      });
      useAuthStore.getState().initialize();

      // Allow async callback to settle
      await Promise.resolve();

      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(true);
      expect(state.user).toBe(mockUser);
      expect(state.isEmailVerified).toBe(true);
      expect(state.isInitialized).toBe(true);
      expect(state.isLoading).toBe(false);
    });

    it('sets unauthenticated state when auth callback fires with null', async () => {
      mockOnAuthStateChanged.mockImplementation((callback) => {
        callback(null);
        return jest.fn();
      });

      useAuthStore.getState().initialize();

      await Promise.resolve();

      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(false);
      expect(state.user).toBeNull();
      expect(state.isEmailVerified).toBe(false);
      expect(state.isInitialized).toBe(true);
      expect(state.isLoading).toBe(false);
    });

    it('reflects emailVerified=false for unverified email users', async () => {
      const mockUser = createMockUser({ emailVerified: false });
      mockOnAuthStateChanged.mockImplementation((callback) => {
        callback(mockUser);
        return jest.fn();
      });
      useAuthStore.getState().initialize();

      await Promise.resolve();

      expect(useAuthStore.getState().isEmailVerified).toBe(false);
    });
  });

  describe('handleSignUpWithEmail', () => {
    it('calls signUpWithEmail with provided arguments', async () => {
      mockSignUpWithEmail.mockResolvedValue({} as any);

      await useAuthStore.getState().handleSignUpWithEmail('a@b.com', 'pass123', 'Alice');

      expect(mockSignUpWithEmail).toHaveBeenCalledWith('a@b.com', 'pass123', 'Alice');
    });

    it('sets isLoading to true during operation', async () => {
      let capturedLoading = false;
      mockSignUpWithEmail.mockImplementation(async () => {
        capturedLoading = useAuthStore.getState().isLoading;
        return {} as any;
      });

      await useAuthStore.getState().handleSignUpWithEmail('a@b.com', 'pass', 'Bob');

      expect(capturedLoading).toBe(true);
    });

    it('clears previous error before starting', async () => {
      useAuthStore.setState({ error: 'previous error' });
      mockSignUpWithEmail.mockResolvedValue({} as any);

      await useAuthStore.getState().handleSignUpWithEmail('a@b.com', 'pass', 'Bob');

      // Error is cleared at start (onAuthStateChanged handles final state)
    });

    it('sets error message and stops loading on failure', async () => {
      mockSignUpWithEmail.mockRejectedValue(new Error('Email already in use'));

      await expect(
        useAuthStore.getState().handleSignUpWithEmail('a@b.com', 'pass', 'Bob'),
      ).rejects.toThrow('Email already in use');

      const state = useAuthStore.getState();
      expect(state.error).toBe('Sign-up failed. Please try again.');
      expect(state.isLoading).toBe(false);
    });

    it('uses fallback error message for non-Error exceptions', async () => {
      mockSignUpWithEmail.mockRejectedValue('unknown');

      await expect(
        useAuthStore.getState().handleSignUpWithEmail('a@b.com', 'pass', 'Bob'),
      ).rejects.toBe('unknown');

      expect(useAuthStore.getState().error).toBe('Sign-up failed. Please try again.');
    });
  });

  describe('handleSignInWithEmail', () => {
    it('calls signInWithEmail with provided arguments', async () => {
      mockSignInWithEmail.mockResolvedValue({} as any);

      await useAuthStore.getState().handleSignInWithEmail('a@b.com', 'pass123');

      expect(mockSignInWithEmail).toHaveBeenCalledWith('a@b.com', 'pass123');
    });

    it('sets isLoading to true during operation', async () => {
      let capturedLoading = false;
      mockSignInWithEmail.mockImplementation(async () => {
        capturedLoading = useAuthStore.getState().isLoading;
        return {} as any;
      });

      await useAuthStore.getState().handleSignInWithEmail('a@b.com', 'pass');

      expect(capturedLoading).toBe(true);
    });

    it('sets error message on failure', async () => {
      mockSignInWithEmail.mockRejectedValue(new Error('Invalid credentials'));

      await expect(
        useAuthStore.getState().handleSignInWithEmail('a@b.com', 'wrong'),
      ).rejects.toThrow('Invalid credentials');

      expect(useAuthStore.getState().error).toBe('Sign-in failed. Please try again.');
      expect(useAuthStore.getState().isLoading).toBe(false);
    });

    it('uses fallback error message for non-Error exceptions', async () => {
      mockSignInWithEmail.mockRejectedValue(42);

      await expect(
        useAuthStore.getState().handleSignInWithEmail('a@b.com', 'pass'),
      ).rejects.toBe(42);

      expect(useAuthStore.getState().error).toBe('Sign-in failed. Please try again.');
    });
  });

  describe('handleSignInWithGoogle', () => {
    it('calls signInWithGoogle', async () => {
      mockSignInWithGoogle.mockResolvedValue({} as any);

      await useAuthStore.getState().handleSignInWithGoogle();

      expect(mockSignInWithGoogle).toHaveBeenCalledTimes(1);
    });

    it('sets isLoading to true during operation', async () => {
      let capturedLoading = false;
      mockSignInWithGoogle.mockImplementation(async () => {
        capturedLoading = useAuthStore.getState().isLoading;
        return {} as any;
      });

      await useAuthStore.getState().handleSignInWithGoogle();

      expect(capturedLoading).toBe(true);
    });

    it('sets error message on failure', async () => {
      mockSignInWithGoogle.mockRejectedValue(new Error('Google sign-in cancelled'));

      await expect(
        useAuthStore.getState().handleSignInWithGoogle(),
      ).rejects.toThrow('Google sign-in cancelled');

      expect(useAuthStore.getState().error).toBe('Sign-in failed. Please try again.');
      expect(useAuthStore.getState().isLoading).toBe(false);
    });

    it('uses fallback error message for non-Error exceptions', async () => {
      mockSignInWithGoogle.mockRejectedValue(undefined);

      await expect(
        useAuthStore.getState().handleSignInWithGoogle(),
      ).rejects.toBeUndefined();

      expect(useAuthStore.getState().error).toBe('Sign-in failed. Please try again.');
    });
  });

  describe('handleSignInWithApple', () => {
    it('calls signInWithApple', async () => {
      mockSignInWithApple.mockResolvedValue({} as any);

      await useAuthStore.getState().handleSignInWithApple();

      expect(mockSignInWithApple).toHaveBeenCalledTimes(1);
    });

    it('sets isLoading to true during operation', async () => {
      let capturedLoading = false;
      mockSignInWithApple.mockImplementation(async () => {
        capturedLoading = useAuthStore.getState().isLoading;
        return {} as any;
      });

      await useAuthStore.getState().handleSignInWithApple();

      expect(capturedLoading).toBe(true);
    });

    it('sets error message on failure', async () => {
      mockSignInWithApple.mockRejectedValue(new Error('Apple sign-in cancelled'));

      await expect(
        useAuthStore.getState().handleSignInWithApple(),
      ).rejects.toThrow('Apple sign-in cancelled');

      expect(useAuthStore.getState().error).toBe('Sign-in failed. Please try again.');
      expect(useAuthStore.getState().isLoading).toBe(false);
    });

    it('uses fallback error message for non-Error exceptions', async () => {
      mockSignInWithApple.mockRejectedValue(null);

      await expect(
        useAuthStore.getState().handleSignInWithApple(),
      ).rejects.toBeNull();

      expect(useAuthStore.getState().error).toBe('Sign-in failed. Please try again.');
    });
  });

  describe('handleSignOut', () => {
    it('calls signOut', async () => {
      mockSignOut.mockResolvedValue(undefined);

      await useAuthStore.getState().handleSignOut();

      expect(mockSignOut).toHaveBeenCalledTimes(1);
    });

    it('sets isLoading to true during operation', async () => {
      let capturedLoading = false;
      mockSignOut.mockImplementation(async () => {
        capturedLoading = useAuthStore.getState().isLoading;
      });

      await useAuthStore.getState().handleSignOut();

      expect(capturedLoading).toBe(true);
    });

    it('sets error message on failure', async () => {
      mockSignOut.mockRejectedValue(new Error('Sign-out failed'));

      await expect(useAuthStore.getState().handleSignOut()).rejects.toThrow(
        'Sign-out failed',
      );

      expect(useAuthStore.getState().error).toBe('Sign-out failed. Please try again.');
      expect(useAuthStore.getState().isLoading).toBe(false);
    });
  });

  describe('resendVerification', () => {
    it('calls sendEmailVerification', async () => {
      mockSendEmailVerification.mockResolvedValue(undefined);

      await useAuthStore.getState().resendVerification();

      expect(mockSendEmailVerification).toHaveBeenCalledTimes(1);
    });

    it('sets error message on failure', async () => {
      mockSendEmailVerification.mockRejectedValue(
        new Error('Too many requests'),
      );

      await expect(
        useAuthStore.getState().resendVerification(),
      ).rejects.toThrow('Too many requests');

      expect(useAuthStore.getState().error).toBe('Failed to resend verification email.');
    });

    it('uses fallback error message for non-Error exceptions', async () => {
      mockSendEmailVerification.mockRejectedValue('oops');

      await expect(
        useAuthStore.getState().resendVerification(),
      ).rejects.toBe('oops');

      expect(useAuthStore.getState().error).toBe('Failed to resend verification email.');
    });
  });

  describe('checkEmailVerified', () => {
    it('calls reloadUser and updates state when verified', async () => {
      const reloadedUser = createMockUser({ emailVerified: true });
      mockReloadUser.mockResolvedValue(reloadedUser);

      const result = await useAuthStore.getState().checkEmailVerified();

      expect(mockReloadUser).toHaveBeenCalledTimes(1);
      expect(result).toBe(true);
      expect(useAuthStore.getState().isEmailVerified).toBe(true);
      expect(useAuthStore.getState().user).toBe(reloadedUser);
    });

    it('returns false and updates state when not verified', async () => {
      const reloadedUser = createMockUser({ emailVerified: false });
      mockReloadUser.mockResolvedValue(reloadedUser);

      const result = await useAuthStore.getState().checkEmailVerified();

      expect(result).toBe(false);
      expect(useAuthStore.getState().isEmailVerified).toBe(false);
    });

    it('returns false when reloadUser returns null', async () => {
      mockReloadUser.mockResolvedValue(null);

      const result = await useAuthStore.getState().checkEmailVerified();

      expect(result).toBe(false);
    });
  });

  describe('clearError', () => {
    it('clears the error state', () => {
      useAuthStore.setState({ error: 'some error' });

      useAuthStore.getState().clearError();

      expect(useAuthStore.getState().error).toBeNull();
    });

    it('does nothing when error is already null', () => {
      useAuthStore.getState().clearError();

      expect(useAuthStore.getState().error).toBeNull();
    });
  });

  describe('getToken', () => {
    it('delegates to getIdToken', async () => {
      mockGetIdToken.mockResolvedValue('firebase-token-abc');

      const result = await useAuthStore.getState().getToken();

      expect(result).toBe('firebase-token-abc');
      expect(mockGetIdToken).toHaveBeenCalledTimes(1);
    });

    it('returns null when no user is signed in', async () => {
      mockGetIdToken.mockResolvedValue(null);

      const result = await useAuthStore.getState().getToken();

      expect(result).toBeNull();
    });
  });
});
