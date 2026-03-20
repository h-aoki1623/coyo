import { View, Text, StyleSheet } from 'react-native';

import { Colors } from '@/constants/colors';
import { Typography } from '@/constants/typography';

interface Props {
  label: string;
}

export function SectionDivider({ label }: Props) {
  return (
    <View style={styles.container}>
      <View style={styles.line} />
      <Text style={styles.label}>{label}</Text>
      <View style={styles.line} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
  },
  line: {
    flex: 1,
    height: 1,
    backgroundColor: Colors.borderSubtle,
  },
  label: {
    ...Typography.captionSmall.ja,
    color: Colors.chevron,
    paddingHorizontal: 8,
  },
});
