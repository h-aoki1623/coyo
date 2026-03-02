import { View, Text, Pressable, StyleSheet } from 'react-native';
import { Colors } from '@/constants/colors';
import { Typography } from '@/constants/typography';

interface Props {
  tabs: readonly string[];
  selectedIndex: number;
  onSelect: (index: number) => void;
}

/**
 * Tab bar with underline style matching the Figma design.
 * Active tab has blue text with a blue bottom border (inset 16px from edges).
 * Inactive tab has gray text with no border.
 */
export function SegmentedControl({ tabs, selectedIndex, onSelect }: Props) {
  return (
    <View style={styles.container} accessibilityRole="tablist">
      {tabs.map((tab, index) => {
        const isSelected = index === selectedIndex;
        return (
          <Pressable
            key={tab}
            style={styles.tab}
            onPress={() => onSelect(index)}
            accessibilityRole="tab"
            accessibilityLabel={tab}
            accessibilityState={{ selected: isSelected }}
          >
            <Text style={[styles.tabText, isSelected && styles.tabTextSelected]}>
              {tab}
            </Text>
            {isSelected && <View style={styles.underline} />}
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    borderBottomWidth: 1,
    borderBottomColor: Colors.borderDefault,
  },
  tab: {
    flex: 1,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  tabText: {
    ...Typography.bodySmall.ja,
    color: Colors.textTertiary,
  },
  tabTextSelected: {
    color: Colors.buttonGhostText,
  },
  underline: {
    position: 'absolute',
    bottom: -1,
    left: 16,
    right: 16,
    height: 2,
    borderRadius: 1,
    backgroundColor: Colors.buttonPrimaryBg,
  },
});
