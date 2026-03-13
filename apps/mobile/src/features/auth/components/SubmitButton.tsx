import { Text, Pressable, ActivityIndicator, StyleSheet } from 'react-native';

import { Colors } from '@/constants/colors';
import { Typography } from '@/constants/typography';

interface Props {
  label: string;
  onPress: () => void;
  disabled?: boolean;
  isLoading?: boolean;
  testID?: string;
}

export function SubmitButton({ label, onPress, disabled, isLoading, testID }: Props) {
  const isDisabled = disabled || isLoading;

  return (
    <Pressable
      style={({ pressed }) => [
        styles.button,
        isDisabled && styles.buttonDisabled,
        pressed && !isDisabled && styles.buttonPressed,
      ]}
      onPress={onPress}
      disabled={isDisabled}
      accessibilityRole="button"
      accessibilityLabel={label}
      testID={testID}
    >
      {isLoading ? (
        <ActivityIndicator size="small" color={Colors.textInverse} />
      ) : (
        <Text style={styles.buttonText}>{label}</Text>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    backgroundColor: Colors.buttonPrimaryBg,
    height: 48,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 20,
  },
  buttonDisabled: {
    opacity: 0.5,
  },
  buttonPressed: {
    opacity: 0.8,
  },
  buttonText: {
    ...Typography.body.ja,
    color: Colors.textInverse,
  },
});
