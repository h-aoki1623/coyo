import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react-native';

import { SuggestionCard } from '../SuggestionCard';
import type { TopicSuggestion } from '@/types/suggestion';

// Mock the SpeechBubbleIcon to avoid SVG rendering issues in tests
jest.mock('@/components/icons', () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { View } = require('react-native');
  return {
    SpeechBubbleIcon: (_props: { size: number; color: string }) => (
      <View testID="speech-bubble-icon" />
    ),
  };
});

const mockSuggestion: TopicSuggestion = {
  id: 'sug-1',
  title: 'Latest NBA Highlights',
  summary: 'Discuss the most exciting plays from last night',
  sourceKeyword: 'basketball',
  pool: 'common',
  rank: 1,
};

describe('SuggestionCard', () => {
  const defaultProps = {
    suggestion: mockSuggestion,
    onPress: jest.fn(),
    isLoading: false,
    isDisabled: false,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders the title text', () => {
    render(<SuggestionCard {...defaultProps} />);

    expect(screen.getByText('Latest NBA Highlights')).toBeTruthy();
  });

  it('renders the summary text', () => {
    render(<SuggestionCard {...defaultProps} />);

    expect(
      screen.getByText('Discuss the most exciting plays from last night'),
    ).toBeTruthy();
  });

  it('renders the source keyword badge', () => {
    render(<SuggestionCard {...defaultProps} />);

    expect(screen.getByText('basketball')).toBeTruthy();
  });

  it('calls onPress with the suggestion when tapped', () => {
    const onPress = jest.fn();
    render(<SuggestionCard {...defaultProps} onPress={onPress} />);

    fireEvent.press(screen.getByRole('button', { name: 'Latest NBA Highlights' }));

    expect(onPress).toHaveBeenCalledTimes(1);
    expect(onPress).toHaveBeenCalledWith(mockSuggestion);
  });

  it('shows ActivityIndicator when isLoading is true', () => {
    render(<SuggestionCard {...defaultProps} isLoading />);

    // The keyword badge should not be visible when loading
    expect(screen.queryByText('basketball')).toBeNull();
  });

  it('hides keyword badge when isLoading is true', () => {
    render(<SuggestionCard {...defaultProps} isLoading />);

    // Title and summary are still visible during loading
    expect(screen.getByText('Latest NBA Highlights')).toBeTruthy();
    expect(
      screen.getByText('Discuss the most exciting plays from last night'),
    ).toBeTruthy();
    // But the keyword badge is replaced by the spinner
    expect(screen.queryByText('basketball')).toBeNull();
  });

  it('is disabled when isDisabled is true', () => {
    const onPress = jest.fn();
    render(<SuggestionCard {...defaultProps} onPress={onPress} isDisabled />);

    fireEvent.press(screen.getByRole('button', { name: 'Latest NBA Highlights' }));

    expect(onPress).not.toHaveBeenCalled();
  });

  it('sets the correct testID based on suggestion id', () => {
    render(<SuggestionCard {...defaultProps} />);

    expect(screen.getByTestId('suggestion-sug-1')).toBeTruthy();
  });

  it('has accessibility role of button', () => {
    render(<SuggestionCard {...defaultProps} />);

    expect(
      screen.getByRole('button', { name: 'Latest NBA Highlights' }),
    ).toBeTruthy();
  });

  it('renders with a different suggestion', () => {
    const otherSuggestion: TopicSuggestion = {
      id: 'sug-2',
      title: 'Tech Trends 2026',
      summary: 'What new gadgets are coming this year',
      sourceKeyword: 'technology',
      pool: 'personal',
      rank: 2,
    };

    render(
      <SuggestionCard
        {...defaultProps}
        suggestion={otherSuggestion}
      />,
    );

    expect(screen.getByText('Tech Trends 2026')).toBeTruthy();
    expect(screen.getByText('What new gadgets are coming this year')).toBeTruthy();
    expect(screen.getByText('technology')).toBeTruthy();
    expect(screen.getByTestId('suggestion-sug-2')).toBeTruthy();
  });
});
