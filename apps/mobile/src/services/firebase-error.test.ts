import { getFirebaseErrorMessage, isSignInCancelled } from './firebase-error';

describe('getFirebaseErrorMessage', () => {
  it('maps auth/email-already-in-use to the expected message', () => {
    expect(
      getFirebaseErrorMessage({ code: 'auth/email-already-in-use' }, 'fallback'),
    ).toBe('This email address is already registered.');
  });

  it('maps auth/invalid-action-code to the password-reset invalid message', () => {
    expect(
      getFirebaseErrorMessage({ code: 'auth/invalid-action-code' }, 'fallback'),
    ).toBe('This link is invalid. Please request a new password reset.');
  });

  it('maps auth/expired-action-code to the expired link message', () => {
    expect(
      getFirebaseErrorMessage({ code: 'auth/expired-action-code' }, 'fallback'),
    ).toBe('This link has expired. Please request a new password reset.');
  });

  it('maps auth/too-many-requests', () => {
    expect(
      getFirebaseErrorMessage({ code: 'auth/too-many-requests' }, 'fallback'),
    ).toBe('Too many attempts. Please try again later.');
  });

  it('returns the fallback when the code is unknown', () => {
    expect(
      getFirebaseErrorMessage({ code: 'auth/unknown-code' }, 'fallback message'),
    ).toBe('fallback message');
  });

  it('returns the fallback when error has no code property', () => {
    expect(getFirebaseErrorMessage(new Error('boom'), 'fallback')).toBe('fallback');
    expect(getFirebaseErrorMessage(null, 'fallback')).toBe('fallback');
    expect(getFirebaseErrorMessage(undefined, 'fallback')).toBe('fallback');
    expect(getFirebaseErrorMessage('raw string', 'fallback')).toBe('fallback');
  });
});

describe('isSignInCancelled', () => {
  it('returns true for Google cancel codes', () => {
    expect(isSignInCancelled({ code: 'SIGN_IN_CANCELLED' })).toBe(true);
  });

  it('returns true for Apple cancel codes', () => {
    expect(isSignInCancelled({ code: 'ERR_REQUEST_CANCELED' })).toBe(true);
    expect(isSignInCancelled({ code: '1000' })).toBe(true);
    expect(isSignInCancelled({ code: 1000 })).toBe(true); // coerced to string
  });

  it('returns false for non-cancel error codes', () => {
    expect(isSignInCancelled({ code: 'auth/invalid-action-code' })).toBe(false);
  });

  it('returns false for values without a code property', () => {
    expect(isSignInCancelled(null)).toBe(false);
    expect(isSignInCancelled(undefined)).toBe(false);
    expect(isSignInCancelled('SIGN_IN_CANCELLED')).toBe(false);
  });
});
