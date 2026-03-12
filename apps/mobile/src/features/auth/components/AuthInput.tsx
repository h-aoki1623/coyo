import { Platform, TextInput, StyleSheet } from 'react-native';

import { Colors } from '@/constants/colors';
import { Typography } from '@/constants/typography';

import type { KeyboardTypeOptions } from 'react-native';

interface Props {
  placeholder: string;
  value: string;
  onChangeText: (text: string) => void;
  secureTextEntry?: boolean;
  keyboardType?: KeyboardTypeOptions;
  autoCapitalize?: 'none' | 'sentences' | 'words' | 'characters';
  testID?: string;
}

export function AuthInput({
  placeholder,
  value,
  onChangeText,
  secureTextEntry,
  keyboardType,
  autoCapitalize,
  testID,
}: Props) {
  // iOS detects secureTextEntry fields as password inputs and shows
  // "Automatic Strong Password". Using textContentType="oneTimeCode"
  // is the only reliable way to suppress this on all iOS versions.
  const contentType = secureTextEntry && Platform.OS === 'ios'
    ? 'oneTimeCode' as const
    : 'none' as const;

  return (
    <TextInput
      style={styles.input}
      value={value}
      onChangeText={onChangeText}
      placeholder={placeholder}
      placeholderTextColor={Colors.textTertiary}
      secureTextEntry={secureTextEntry}
      keyboardType={keyboardType}
      autoCapitalize={autoCapitalize}
      textContentType={contentType}
      autoComplete="off"
      importantForAutofill="no"
      autoCorrect={false}
      accessibilityLabel={placeholder}
      testID={testID}
    />
  );
}

const styles = StyleSheet.create({
  input: {
    ...Typography.body.ja,
    height: 48,
    backgroundColor: Colors.surfaceElevated,
    borderRadius: 14,
    paddingHorizontal: 16,
    color: Colors.textPrimary,
  },
});
