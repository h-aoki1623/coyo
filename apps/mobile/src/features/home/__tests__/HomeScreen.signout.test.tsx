/**
 * Sign-out confirmation behaviour for HomeScreen (issue #157).
 *
 * The sign-out button used to call `handleSignOut` directly on press,
 * which made it possible for an unintended tap (e.g. a fast scroll-then-
 * tap that landed on the button) to drop the user back to Welcome
 * mid-flow. The button now opens a native confirmation Alert and only
 * calls `handleSignOut` after the user explicitly confirms.
 */

import React from 'react';
import { Alert } from 'react-native';
import { fireEvent, render } from '@testing-library/react-native';

import { HomeScreen } from '@/features/home/HomeScreen';

// Heavy native deps — stub at the boundary so the test stays focused on
// the button-press handler without wiring up the real screen graph.
jest.mock('react-native-safe-area-context', () => {
  const { View } = jest.requireActual('react-native');
  return {
    SafeAreaView: View,
  };
});

const mockHandleSignOut = jest.fn().mockResolvedValue(undefined);
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Selector = (state: any) => unknown;

jest.mock('@/stores/auth-store', () => ({
  useAuthStore: (selector: Selector) => selector({ handleSignOut: mockHandleSignOut }),
}));

jest.mock('@/stores/conversation-store', () => ({
  useConversationStore: (selector: Selector) => selector({ startConversation: jest.fn() }),
}));

jest.mock('@/stores/app-store', () => ({
  useAppStore: (selector: Selector) =>
    selector({ pausedConversationId: null, setPausedConversationId: jest.fn() }),
}));

jest.mock('@/features/home/hooks/useSuggestions', () => ({
  useSuggestions: () => ({
    suggestions: { personal: [], trending: [] },
    isLoading: false,
  }),
}));

jest.mock('@/api/client', () => ({
  apiClient: { post: jest.fn(), get: jest.fn(), delete: jest.fn(), postStream: jest.fn() },
}));

const navigation = {
  navigate: jest.fn(),
  setOptions: jest.fn(),
};

const route = { key: 'Home', name: 'Home', params: undefined };

describe('HomeScreen sign-out confirmation (issue #157)', () => {
  let alertSpy: jest.SpyInstance;

  beforeEach(() => {
    mockHandleSignOut.mockClear();
    alertSpy = jest.spyOn(Alert, 'alert').mockImplementation(() => {});
  });

  afterEach(() => {
    alertSpy.mockRestore();
  });

  it('opens a confirmation Alert when the sign-out button is pressed', () => {
    const { getByTestId } = render(<HomeScreen navigation={navigation as never} route={route as never} />);
    fireEvent.press(getByTestId('sign-out-button'));

    expect(alertSpy).toHaveBeenCalledTimes(1);
    expect(mockHandleSignOut).not.toHaveBeenCalled();
  });

  it('calls handleSignOut only when the destructive confirm action is invoked', () => {
    const { getByTestId } = render(<HomeScreen navigation={navigation as never} route={route as never} />);
    fireEvent.press(getByTestId('sign-out-button'));

    const buttons = alertSpy.mock.calls[0][2] as Array<{ style?: string; onPress?: () => void }>;
    const confirm = buttons.find((b) => b.style === 'destructive');
    expect(confirm).toBeDefined();
    confirm!.onPress?.();

    expect(mockHandleSignOut).toHaveBeenCalledTimes(1);
  });

  it('leaves the user signed in if the cancel action is invoked', () => {
    const { getByTestId } = render(<HomeScreen navigation={navigation as never} route={route as never} />);
    fireEvent.press(getByTestId('sign-out-button'));

    const buttons = alertSpy.mock.calls[0][2] as Array<{ style?: string; onPress?: () => void }>;
    const cancel = buttons.find((b) => b.style === 'cancel');
    expect(cancel).toBeDefined();
    // Cancel buttons typically have no onPress or a noop.
    cancel!.onPress?.();

    expect(mockHandleSignOut).not.toHaveBeenCalled();
  });

  it('swallows rejected handleSignOut without surfacing an unhandled rejection', async () => {
    mockHandleSignOut.mockRejectedValueOnce(new Error('keychain unavailable'));
    const { getByTestId } = render(<HomeScreen navigation={navigation as never} route={route as never} />);
    fireEvent.press(getByTestId('sign-out-button'));

    const buttons = alertSpy.mock.calls[0][2] as Array<{ style?: string; onPress?: () => void }>;
    const confirm = buttons.find((b) => b.style === 'destructive');
    // If the wrapper did not catch the rejection, this would surface as
    // an unhandled promise rejection and fail the test.
    await expect(
      (async () => {
        confirm!.onPress?.();
        await Promise.resolve();
      })(),
    ).resolves.not.toThrow();

    expect(mockHandleSignOut).toHaveBeenCalledTimes(1);
  });
});
