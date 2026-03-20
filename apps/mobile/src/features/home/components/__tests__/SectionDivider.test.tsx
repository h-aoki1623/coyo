import React from 'react';
import { render, screen } from '@testing-library/react-native';

import { SectionDivider } from '../SectionDivider';

describe('SectionDivider', () => {
  it('renders the label text', () => {
    render(<SectionDivider label="Trending" />);

    expect(screen.getByText('Trending')).toBeTruthy();
  });

  it('renders with a different label', () => {
    render(<SectionDivider label="For You" />);

    expect(screen.getByText('For You')).toBeTruthy();
  });

  it('renders the correct structure with container and lines', () => {
    const { toJSON } = render(<SectionDivider label="Trending" />);
    const tree = toJSON();

    // Root View (container) should have 3 children: line, text, line
    expect(tree).not.toBeNull();
    expect((tree as { children: unknown[] }).children).toHaveLength(3);
  });

  it('handles empty label string', () => {
    const { toJSON } = render(<SectionDivider label="" />);

    // Should render without crashing even with empty label
    expect(toJSON()).not.toBeNull();
  });

  it('handles special characters in label', () => {
    render(<SectionDivider label={'\u304A\u3059\u3059\u3081 & More!'} />);

    expect(screen.getByText('\u304A\u3059\u3059\u3081 & More!')).toBeTruthy();
  });
});
