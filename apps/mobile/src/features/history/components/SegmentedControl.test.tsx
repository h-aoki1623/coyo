import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react-native';
import { SegmentedControl } from './SegmentedControl';

describe('SegmentedControl', () => {
  const defaultTabs = ['Tab A', 'Tab B'] as const;

  it('renders all tab labels', () => {
    render(
      <SegmentedControl
        tabs={defaultTabs}
        selectedIndex={0}
        onSelect={jest.fn()}
      />,
    );

    expect(screen.getByText('Tab A')).toBeTruthy();
    expect(screen.getByText('Tab B')).toBeTruthy();
  });

  it('calls onSelect with correct index when a tab is pressed', () => {
    const onSelect = jest.fn();
    render(
      <SegmentedControl
        tabs={defaultTabs}
        selectedIndex={0}
        onSelect={onSelect}
      />,
    );

    fireEvent.press(screen.getByText('Tab B'));

    expect(onSelect).toHaveBeenCalledWith(1);
  });

  it('calls onSelect with index 0 when the first tab is pressed', () => {
    const onSelect = jest.fn();
    render(
      <SegmentedControl
        tabs={defaultTabs}
        selectedIndex={1}
        onSelect={onSelect}
      />,
    );

    fireEvent.press(screen.getByText('Tab A'));

    expect(onSelect).toHaveBeenCalledWith(0);
  });

  it('sets accessibility role to tab for each tab', () => {
    render(
      <SegmentedControl
        tabs={defaultTabs}
        selectedIndex={0}
        onSelect={jest.fn()}
      />,
    );

    const tabs = screen.getAllByRole('tab');
    expect(tabs).toHaveLength(2);
  });

  it('marks the selected tab with selected accessibility state', () => {
    render(
      <SegmentedControl
        tabs={defaultTabs}
        selectedIndex={0}
        onSelect={jest.fn()}
      />,
    );

    // The selected tab should be queryable by its selected state
    const selectedTab = screen.getByRole('tab', { name: 'Tab A', selected: true });
    expect(selectedTab).toBeTruthy();

    // The unselected tab should not be selected
    const unselectedTab = screen.getByRole('tab', { name: 'Tab B', selected: false });
    expect(unselectedTab).toBeTruthy();
  });

  it('renders with three tabs', () => {
    const threeTabs = ['One', 'Two', 'Three'] as const;
    render(
      <SegmentedControl
        tabs={threeTabs}
        selectedIndex={2}
        onSelect={jest.fn()}
      />,
    );

    expect(screen.getByText('One')).toBeTruthy();
    expect(screen.getByText('Two')).toBeTruthy();
    expect(screen.getByText('Three')).toBeTruthy();
  });

  it('does not call onSelect on render', () => {
    const onSelect = jest.fn();
    render(
      <SegmentedControl
        tabs={defaultTabs}
        selectedIndex={0}
        onSelect={onSelect}
      />,
    );

    expect(onSelect).not.toHaveBeenCalled();
  });
});
