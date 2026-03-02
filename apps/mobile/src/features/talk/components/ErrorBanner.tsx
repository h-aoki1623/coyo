import { View, Text, Pressable, StyleSheet } from 'react-native';
import { Colors } from '@/constants/colors';
import { Typography } from '@/constants/typography';
import { t } from '@/i18n';
import { HintIcon } from '@/components/icons';

interface Props {
  message: string;
  onRetry: () => void;
}

/**
 * Error banner displayed in the message area when a recognition error occurs.
 * Rounded card with icon circle, message text, and retry button.
 */
export function ErrorBanner({ message, onRetry }: Props) {
  return (
    <View style={styles.container}>
      <View style={styles.content}>
        <View style={styles.iconCircle}>
          <HintIcon size={16} color={Colors.statusError} />
        </View>
        <Text style={styles.message}>{message}</Text>
        <Pressable
          style={styles.retryButton}
          onPress={onRetry}
          accessibilityRole="button"
          accessibilityLabel={t('common.retry')}
        >
          <Text style={styles.retryText}>{t('common.retry')}</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: 20,
  },
  content: {
    backgroundColor: Colors.statusErrorBg,
    borderWidth: 1,
    borderColor: Colors.statusError,
    borderRadius: 14,
    paddingHorizontal: 17,
    paddingVertical: 13,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  iconCircle: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: '#FEE2E2',
    justifyContent: 'center',
    alignItems: 'center',
  },
  message: {
    ...Typography.body.ja,
    color: Colors.textPrimary,
    flex: 1,
  },
  retryButton: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  retryText: {
    ...Typography.body.ja,
    color: Colors.buttonGhostText,
  },
});
