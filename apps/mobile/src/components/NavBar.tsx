import { View, Text, Pressable, StyleSheet } from 'react-native';
import { BackIcon } from '@/components/icons';
import { Colors } from '@/constants/colors';
import { Typography } from '@/constants/typography';

interface Props {
  title: string;
  onBack?: () => void;
  testID?: string;
}

export function NavBar({ title, onBack, testID }: Props) {
  return (
    <View style={styles.container}>
      {onBack ? (
        <Pressable
          onPress={onBack}
          style={styles.backButton}
          accessibilityRole="button"
          accessibilityLabel="Go back"
          testID="nav-back"
        >
          <BackIcon size={16} color={Colors.buttonGhostText} />
        </Pressable>
      ) : (
        <View style={styles.spacer} />
      )}
      <Text style={styles.title} testID={testID}>{title}</Text>
      <View style={styles.spacer} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    height: 56,
    paddingHorizontal: 20,
  },
  backButton: {
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: {
    ...Typography.title.ja,
    color: Colors.textPrimary,
    textAlign: 'center',
  },
  spacer: {
    width: 40,
    height: 40,
  },
});
