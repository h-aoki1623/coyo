import React from 'react';
import { render, screen } from '@testing-library/react-native';
import { ErrorBanner } from './ErrorBanner';

describe('ErrorBanner', () => {
  it('renders the error message text', () => {
    render(<ErrorBanner message="Something went wrong" />);

    expect(screen.getByText('Something went wrong')).toBeTruthy();
  });

  it('renders with an empty message', () => {
    render(<ErrorBanner message="" />);

    // Component still renders, just with empty text
    expect(screen.toJSON()).toBeTruthy();
  });

  it('renders special characters and unicode', () => {
    const message = 'Error: invalid email \u2014 try again';
    render(<ErrorBanner message={message} />);

    expect(screen.getByText(message)).toBeTruthy();
  });

  it('renders a long error message', () => {
    const longMessage = 'A'.repeat(500);
    render(<ErrorBanner message={longMessage} />);

    expect(screen.getByText(longMessage)).toBeTruthy();
  });
});
