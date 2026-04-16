import { useAuthStore } from './auth-store';

jest.mock('@/services/firebase-auth', () => ({
  configureGoogleSignIn: jest.fn(),
  onAuthStateChanged: jest.fn(() => jest.fn()),
  signUpWithEmail: jest.fn(),
  signInWithEmail: jest.fn(),
  signInWithGoogle: jest.fn(),
  signInWithApple: jest.fn(),
  signOut: jest.fn(),
  sendEmailVerification: jest.fn(),
  sendPasswordResetEmail: jest.fn(),
  reloadUser: jest.fn(),
  getIdToken: jest.fn(),
}));

jest.mock('@/api/client', () => ({
  apiClient: {
    post: jest.fn(() => Promise.resolve({ data: null })),
    get: jest.fn(),
    delete: jest.fn(),
    postStream: jest.fn(),
  },
}));

jest.mock('@/stores/suggestions-store', () => ({
  useSuggestionsStore: {
    getState: () => ({
      prefetch: jest.fn().mockResolvedValue(undefined),
      reset: jest.fn(),
    }),
  },
}));

import { sendPasswordResetEmail } from '@/services/firebase-auth';

const mockSendPasswordResetEmail = sendPasswordResetEmail as jest.MockedFunction<
  typeof sendPasswordResetEmail
>;

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

describe('useAuthStore — requestPasswordReset', () => {
  beforeEach(() => {
    resetStore();
    jest.clearAllMocks();
  });

  it('calls sendPasswordResetEmail and clears loading on success', async () => {
    mockSendPasswordResetEmail.mockResolvedValue(undefined);

    await useAuthStore.getState().requestPasswordReset('user@example.com');

    expect(mockSendPasswordResetEmail).toHaveBeenCalledWith('user@example.com');
    const state = useAuthStore.getState();
    expect(state.isLoading).toBe(false);
    expect(state.error).toBeNull();
  });

  it('sets loading state during the call', async () => {
    let captured = false;
    mockSendPasswordResetEmail.mockImplementation(async () => {
      captured = useAuthStore.getState().isLoading;
    });

    await useAuthStore.getState().requestPasswordReset('a@b.com');

    expect(captured).toBe(true);
  });

  it('swallows auth/user-not-found silently to prevent account enumeration', async () => {
    mockSendPasswordResetEmail.mockRejectedValue({ code: 'auth/user-not-found' });

    await expect(
      useAuthStore.getState().requestPasswordReset('missing@example.com'),
    ).resolves.toBeUndefined();

    const state = useAuthStore.getState();
    expect(state.error).toBeNull();
    expect(state.isLoading).toBe(false);
  });

  it('uses the password-reset fallback message for unmapped errors', async () => {
    mockSendPasswordResetEmail.mockRejectedValue(new Error('network down'));

    await expect(
      useAuthStore.getState().requestPasswordReset('a@b.com'),
    ).rejects.toThrow('network down');

    expect(useAuthStore.getState().error).toBe('Failed to send password reset email.');
  });
});
