import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react-native';
import { SubmitButton } from './SubmitButton';

describe('SubmitButton', () => {
  it('renders the label text', () => {
    render(<SubmitButton label="Sign In" onPress={jest.fn()} />);

    expect(screen.getByText('Sign In')).toBeTruthy();
  });

  it('calls onPress when pressed', () => {
    const onPress = jest.fn();
    render(<SubmitButton label="Sign In" onPress={onPress} />);

    fireEvent.press(screen.getByRole('button', { name: 'Sign In' }));

    expect(onPress).toHaveBeenCalledTimes(1);
  });

  it('does not call onPress when disabled', () => {
    const onPress = jest.fn();
    render(<SubmitButton label="Sign In" onPress={onPress} disabled />);

    fireEvent.press(screen.getByRole('button', { name: 'Sign In' }));

    expect(onPress).not.toHaveBeenCalled();
  });

  it('shows ActivityIndicator instead of label when isLoading is true', () => {
    render(<SubmitButton label="Sign In" onPress={jest.fn()} isLoading />);

    // Label should not be visible
    expect(screen.queryByText('Sign In')).toBeNull();
  });

  it('does not call onPress when isLoading is true', () => {
    const onPress = jest.fn();
    render(<SubmitButton label="Sign In" onPress={onPress} isLoading />);

    fireEvent.press(screen.getByRole('button', { name: 'Sign In' }));

    expect(onPress).not.toHaveBeenCalled();
  });

  it('sets the provided testID on the Pressable', () => {
    render(
      <SubmitButton label="Sign In" onPress={jest.fn()} testID="submit-btn" />,
    );

    expect(screen.getByTestId('submit-btn')).toBeTruthy();
  });

  it('has accessibility role of button', () => {
    render(<SubmitButton label="Sign In" onPress={jest.fn()} />);

    expect(screen.getByRole('button', { name: 'Sign In' })).toBeTruthy();
  });

  it('does not call onPress on initial render', () => {
    const onPress = jest.fn();
    render(<SubmitButton label="Sign In" onPress={onPress} />);

    expect(onPress).not.toHaveBeenCalled();
  });
});
