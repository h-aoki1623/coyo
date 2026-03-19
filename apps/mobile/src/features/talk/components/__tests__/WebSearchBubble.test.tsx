import React from 'react';
import { render, screen } from '@testing-library/react-native';
import { WebSearchBubble } from '../MessageBubble';

// Mock i18n to return predictable strings
jest.mock('@/i18n', () => ({
  t: (key: string) => {
    const translations: Record<string, string> = {
      'talk.searching': 'Searching...',
    };
    return translations[key] ?? key;
  },
}));

// Mock icon components to avoid SVG rendering issues in tests
jest.mock('@/components/icons', () => ({
  CoyoAvatar: (_props: { size: number; variant?: string }) => {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const { View } = require('react-native');
    return <View testID="coyo-avatar" />;
  },
  SpinnerIcon: () => null,
}));

// Mock react-native-svg to avoid native module errors
jest.mock('react-native-svg', () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { View } = require('react-native');
  return {
    __esModule: true,
    default: View,
    Svg: View,
    Circle: View,
    Line: View,
  };
});

describe('WebSearchBubble', () => {
  it('renders "Searching..." text', () => {
    render(<WebSearchBubble />);

    expect(screen.getByText('Searching...')).toBeTruthy();
  });

  it('has correct accessibility label using t("talk.searching")', () => {
    const { toJSON } = render(<WebSearchBubble />);
    const tree = toJSON();

    // The outer View has accessibilityLabel={t('talk.searching')}
    expect(tree).not.toBeNull();
    expect(
      (tree as { props: Record<string, unknown> }).props.accessibilityLabel,
    ).toBe('Searching...');
  });

  it('has accessibilityRole "text"', () => {
    const { toJSON } = render(<WebSearchBubble />);
    const tree = toJSON();

    expect(tree).not.toBeNull();
    expect(
      (tree as { props: Record<string, unknown> }).props.accessibilityRole,
    ).toBe('text');
  });

  it('renders CoyoAvatar', () => {
    render(<WebSearchBubble />);

    expect(screen.getByTestId('coyo-avatar')).toBeTruthy();
  });

  it('is wrapped in an Animated.View (contains animated child)', () => {
    const { toJSON } = render(<WebSearchBubble />);
    const tree = toJSON() as { children: Array<{ type: string }> };

    // The outer container is a View with two children: CoyoAvatar mock + Animated.View
    expect(tree).not.toBeNull();
    expect(tree.children.length).toBeGreaterThanOrEqual(2);
  });
});
