import { Pressable, Text, View, StyleSheet } from 'react-native';

import { MailIcon, GoogleIcon, AppleIcon } from '@/components/icons';
import { Colors } from '@/constants/colors';
import { Typography } from '@/constants/typography';

type Variant = 'email' | 'google' | 'apple';

interface Props {
  variant: Variant;
  label: string;
  onPress: () => void;
  disabled?: boolean;
  testID?: string;
}

function renderIcon(variant: Variant) {
  switch (variant) {
    case 'email':
      return <MailIcon size={20} color={Colors.textInverse} />;
    case 'google':
      return <GoogleIcon size={20} />;
    case 'apple':
      return <AppleIcon size={20} color={Colors.textInverse} />;
  }
}

export function AuthProviderButton({ variant, label, onPress, disabled, testID }: Props) {
  return (
    <Pressable
      style={({ pressed }) => [
        styles.base,
        variantStyles[variant],
        pressed && styles.pressed,
        disabled && styles.disabled,
      ]}
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={label}
      testID={testID}
    >
      <View style={[styles.iconOverlay, iconOverlayStyles[variant]]}>
        {renderIcon(variant)}
      </View>
      <Text style={[styles.label, variantTextStyles[variant]]}>
        {label}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    height: 48,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  pressed: {
    opacity: 0.8,
  },
  disabled: {
    opacity: 0.5,
  },
  iconOverlay: {
    position: 'absolute',
    left: 16,
    top: 8,
    width: 32,
    height: 32,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  label: {},
});

const iconOverlayStyles = StyleSheet.create({
  email: {
    backgroundColor: 'rgba(255, 255, 255, 0.18)',
  },
  google: {
    backgroundColor: 'transparent',
  },
  apple: {
    backgroundColor: 'rgba(255, 255, 255, 0.10)',
  },
});

const variantStyles = StyleSheet.create({
  email: {
    backgroundColor: Colors.buttonPrimaryBg,
  },
  google: {
    backgroundColor: Colors.surfaceCard,
    borderWidth: 1,
    borderColor: Colors.borderDefault,
  },
  apple: {
    backgroundColor: Colors.textPrimary,
  },
});

const variantTextStyles = StyleSheet.create({
  email: {
    ...Typography.body.ja,
    color: Colors.textInverse,
  },
  google: {
    ...Typography.body.ja,
    color: Colors.textPrimary,
  },
  apple: {
    ...Typography.body.ja,
    color: Colors.textInverse,
  },
});
