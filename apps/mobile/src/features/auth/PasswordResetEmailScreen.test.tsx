import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react-native';

import { PasswordResetEmailScreen } from './PasswordResetEmailScreen';

jest.mock('@/components/NavBar', () => ({
  NavBar: () => null,
}));

// Zustand-like mock: a selector function is called with a state snapshot.
// We expose a `__setState` helper so individual tests can update the state
// surface the component sees.
type StoreShape = {
  isLoading: boolean;
  error: string | null;
  requestPasswordReset: jest.Mock;
  clearError: jest.Mock;
};

let mockStoreState: StoreShape;

jest.mock('@/stores/auth-store', () => ({
  useAuthStore: (selector: (s: StoreShape) => unknown) => selector(mockStoreState),
}));

function makeNavigation() {
  return {
    navigate: jest.fn(),
    goBack: jest.fn(),
    reset: jest.fn(),
  };
}

describe('PasswordResetEmailScreen', () => {
  beforeEach(() => {
    mockStoreState = {
      isLoading: false,
      error: null,
      requestPasswordReset: jest.fn().mockResolvedValue(undefined),
      clearError: jest.fn(),
    };
  });

  it('renders the title, email input, and submit button', () => {
    const navigation = makeNavigation();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    render(<PasswordResetEmailScreen navigation={navigation as any} route={{ key: 'k', name: 'PasswordResetEmail' } as any} />);

    expect(screen.getByText('Reset Password')).toBeTruthy();
    expect(screen.getByTestId('password-reset-email-input')).toBeTruthy();
    expect(screen.getByTestId('password-reset-email-submit')).toBeTruthy();
  });

  it('disables the submit button until a valid email is entered', async () => {
    const navigation = makeNavigation();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    render(<PasswordResetEmailScreen navigation={navigation as any} route={{ key: 'k', name: 'PasswordResetEmail' } as any} />);

    const input = screen.getByTestId('password-reset-email-input');
    const submit = screen.getByTestId('password-reset-email-submit');

    // Empty → disabled → pressing does nothing.
    await act(async () => {
      fireEvent.press(submit);
    });
    expect(mockStoreState.requestPasswordReset).not.toHaveBeenCalled();

    // Invalid email → still disabled.
    fireEvent.changeText(input, 'not-an-email');
    await act(async () => {
      fireEvent.press(submit);
    });
    expect(mockStoreState.requestPasswordReset).not.toHaveBeenCalled();
  });

  it('calls requestPasswordReset and navigates to PasswordResetSent on success', async () => {
    const navigation = makeNavigation();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    render(<PasswordResetEmailScreen navigation={navigation as any} route={{ key: 'k', name: 'PasswordResetEmail' } as any} />);

    const input = screen.getByTestId('password-reset-email-input');
    const submit = screen.getByTestId('password-reset-email-submit');

    fireEvent.changeText(input, '  user@example.com  ');
    await act(async () => {
      fireEvent.press(submit);
    });

    expect(mockStoreState.requestPasswordReset).toHaveBeenCalledWith('user@example.com');
    expect(navigation.navigate).toHaveBeenCalledWith('PasswordResetSent', {
      email: 'user@example.com',
    });
  });

  it('does not navigate when requestPasswordReset throws', async () => {
    mockStoreState.requestPasswordReset.mockRejectedValue(new Error('boom'));
    const navigation = makeNavigation();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    render(<PasswordResetEmailScreen navigation={navigation as any} route={{ key: 'k', name: 'PasswordResetEmail' } as any} />);

    fireEvent.changeText(screen.getByTestId('password-reset-email-input'), 'user@example.com');
    await act(async () => {
      fireEvent.press(screen.getByTestId('password-reset-email-submit'));
    });

    expect(navigation.navigate).not.toHaveBeenCalled();
  });

  it('renders the error message from the auth store', () => {
    mockStoreState.error = 'Something went wrong';
    const navigation = makeNavigation();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    render(<PasswordResetEmailScreen navigation={navigation as any} route={{ key: 'k', name: 'PasswordResetEmail' } as any} />);

    expect(screen.getByText('Something went wrong')).toBeTruthy();
  });

  it('clears pre-existing errors on mount', () => {
    const navigation = makeNavigation();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    render(<PasswordResetEmailScreen navigation={navigation as any} route={{ key: 'k', name: 'PasswordResetEmail' } as any} />);

    expect(mockStoreState.clearError).toHaveBeenCalled();
  });
});
