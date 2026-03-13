import { View, Text, StyleSheet } from 'react-native';

import { Colors } from '@/constants/colors';
import { Typography } from '@/constants/typography';

interface Props {
  message: string;
}

export function ErrorBanner({ message }: Props) {
  return (
    <View style={styles.container}>
      <Text style={styles.text}>{message}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginTop: 16,
    backgroundColor: Colors.statusErrorBg,
    borderRadius: 10,
    padding: 12,
  },
  text: {
    ...Typography.caption.ja,
    color: Colors.statusError,
    textAlign: 'center',
  },
});
