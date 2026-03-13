import React from 'react';
import { Text } from 'react-native';
import { render, screen, fireEvent } from '@testing-library/react-native';
import { AuthFormLayout } from './AuthFormLayout';

jest.mock('@/components/NavBar', () => ({
  NavBar: ({ onBack }: { onBack?: () => void }) => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const RN = require('react-native');
    return (
      <RN.Pressable
        onPress={onBack}
        accessibilityRole="button"
        accessibilityLabel="Go back"
        testID="nav-back"
      >
        <RN.Text>Back</RN.Text>
      </RN.Pressable>
    );
  },
}));

describe('AuthFormLayout', () => {
  it('renders the title text', () => {
    render(
      <AuthFormLayout title="Sign In" onBack={jest.fn()}>
        <Text>Content</Text>
      </AuthFormLayout>,
    );

    expect(screen.getByText('Sign In')).toBeTruthy();
  });

  it('renders children', () => {
    render(
      <AuthFormLayout title="Sign In" onBack={jest.fn()}>
        <Text>Form content here</Text>
      </AuthFormLayout>,
    );

    expect(screen.getByText('Form content here')).toBeTruthy();
  });

  it('renders multiple children', () => {
    render(
      <AuthFormLayout title="Sign In" onBack={jest.fn()}>
        <Text>First child</Text>
        <Text>Second child</Text>
      </AuthFormLayout>,
    );

    expect(screen.getByText('First child')).toBeTruthy();
    expect(screen.getByText('Second child')).toBeTruthy();
  });

  it('calls onBack when the NavBar back button is pressed', () => {
    const onBack = jest.fn();
    render(
      <AuthFormLayout title="Sign In" onBack={onBack}>
        <Text>Content</Text>
      </AuthFormLayout>,
    );

    fireEvent.press(screen.getByTestId('nav-back'));

    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it('does not call onBack on initial render', () => {
    const onBack = jest.fn();
    render(
      <AuthFormLayout title="Sign In" onBack={onBack}>
        <Text>Content</Text>
      </AuthFormLayout>,
    );

    expect(onBack).not.toHaveBeenCalled();
  });
});
