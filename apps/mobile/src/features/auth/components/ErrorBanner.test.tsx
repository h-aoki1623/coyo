import React from 'react';
import { render, screen } from '@testing-library/react-native';
import { ErrorBanner } from './ErrorBanner';

describe('ErrorBanner', () => {
  it('renders the error message text', () => {
    render(<ErrorBanner message="Something went wrong" />);

    expect(screen.getByText('Something went wrong')).toBeTruthy();
  });

  it('returns null for an empty message', () => {
    render(<ErrorBanner message="" />);

    expect(screen.toJSON()).toBeNull();
  });

  it('has accessibilityRole alert', () => {
    const { toJSON } = render(<ErrorBanner message="Error occurred" />);
    const tree = toJSON();

    expect(tree).not.toBeNull();
    expect((tree as { props: Record<string, unknown> }).props.accessibilityRole).toBe('alert');
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
