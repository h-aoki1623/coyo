import { View, Text, StyleSheet } from 'react-native';

import { Colors } from '@/constants/colors';
import { Fonts, Typography } from '@/constants/typography';

interface Props {
  number: number;
  text: string;
}

export function StepItem({ number, text }: Props) {
  return (
    <View style={styles.container}>
      <View style={styles.badge}>
        <Text style={styles.badgeText}>{number}</Text>
      </View>
      <Text style={styles.text}>{text}</Text>
    </View>
  );
}

const BADGE_SIZE = 20;

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
  },
  badge: {
    width: BADGE_SIZE,
    height: BADGE_SIZE,
    borderRadius: BADGE_SIZE / 2,
    backgroundColor: Colors.accentIconBg,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 1,
  },
  badgeText: {
    fontFamily: Fonts.plusJakartaSans.bold,
    fontSize: 11,
    color: Colors.buttonPrimaryBg,
  },
  text: {
    ...Typography.caption.ja,
    color: Colors.textSecondary,
    flex: 1,
  },
});
