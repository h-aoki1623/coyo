import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react-native';

import { PasswordResetSuccessScreen } from './PasswordResetSuccessScreen';

jest.mock('@/components/icons', () => ({
  CheckIcon: () => null,
}));

function makeProps() {
  return {
    navigation: {
      navigate: jest.fn(),
      goBack: jest.fn(),
      reset: jest.fn(),
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any,
    route: {
      key: 'k',
      name: 'PasswordResetSuccess',
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any,
  };
}

describe('PasswordResetSuccessScreen', () => {
  it('renders the success title and description', () => {
    render(<PasswordResetSuccessScreen {...makeProps()} />);
    expect(screen.getByText('Password Updated')).toBeTruthy();
    expect(screen.getByText('You can now sign in with your new password.')).toBeTruthy();
  });

  it('resets navigation to the Welcome screen when the button is pressed', () => {
    const props = makeProps();
    render(<PasswordResetSuccessScreen {...props} />);

    fireEvent.press(screen.getByTestId('password-reset-success-back'));

    expect(props.navigation.reset).toHaveBeenCalledWith({
      index: 0,
      routes: [{ name: 'Welcome' }],
    });
  });
});
