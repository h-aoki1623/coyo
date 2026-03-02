import { View, Text, Pressable, StyleSheet, Platform } from 'react-native';
import { Colors } from '@/constants/colors';
import { Typography } from '@/constants/typography';
import { t } from '@/i18n';
import { MicIcon } from '@/components/icons';

interface Props {
  onPress: () => void;
  disabled?: boolean;
  processing?: boolean;
  processingText?: string;
}

/**
 * Large blue microphone button with a status pill above.
 *
 * Idle state:   dashed pill hint + active blue mic button with shadow.
 * Processing:   dashed pill (muted) + blue mic button at 40% opacity, no shadow.
 *
 * Both states share the same container layout so the button never shifts position.
 */
export function RecordButton({
  onPress,
  disabled = false,
  processing = false,
  processingText,
}: Props) {
  const effectiveDisabled = disabled || processing;
  const label = processing
    ? (processingText ?? t('talk.processingVoice'))
    : t('talk.recordHint');

  return (
    <View style={styles.container}>
      <View style={[styles.hintPill, processing && styles.hintPillProcessing]}>
        <Text style={[styles.hintText, processing && styles.hintTextProcessing]}>
          {label}
        </Text>
      </View>
      <Pressable
        style={({ pressed }) => [
          styles.button,
          processing
            ? styles.buttonProcessing
            : effectiveDisabled
              ? styles.buttonDisabled
              : styles.buttonShadow,
          pressed && !effectiveDisabled && styles.buttonPressed,
        ]}
        onPress={onPress}
        disabled={effectiveDisabled}
        testID="record-button"
        accessibilityRole="button"
        accessibilityLabel={label}
        accessibilityState={{ disabled: effectiveDisabled }}
      >
        <MicIcon size={26} color="#FFFFFF" />
      </Pressable>
    </View>
  );
}

const BUTTON_SIZE = 62;

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    paddingTop: 16,
    paddingBottom: 40,
    gap: 16,
  },
  // -- Pill --
  hintPill: {
    borderWidth: 1,
    borderStyle: 'dashed',
    borderColor: Colors.borderDefault,
    borderRadius: 20,
    paddingHorizontal: 21,
    paddingVertical: 11,
  },
  hintPillProcessing: {
    borderColor: Colors.borderSubtle,
  },
  hintText: {
    ...Typography.bodySmall.en,
    color: Colors.textTertiary,
  },
  hintTextProcessing: {
    color: Colors.chevron,
  },
  // -- Button --
  button: {
    width: BUTTON_SIZE,
    height: BUTTON_SIZE,
    borderRadius: 31,
    backgroundColor: Colors.buttonPrimaryBg,
    justifyContent: 'center',
    alignItems: 'center',
  },
  buttonShadow: {
    ...Platform.select({
      ios: {
        shadowColor: 'rgba(59,130,246,1)',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.35,
        shadowRadius: 20,
      },
      android: {
        elevation: 8,
      },
    }),
  },
  buttonProcessing: {
    opacity: 0.4,
  },
  buttonPressed: {
    opacity: 0.8,
    transform: [{ scale: 0.95 }],
  },
  buttonDisabled: {
    backgroundColor: '#C7C7CC',
  },
});
