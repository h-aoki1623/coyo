import { useCallback } from 'react';
import { View, Text, Pressable, StyleSheet } from 'react-native';
import NetInfo from '@react-native-community/netinfo';
import { Colors } from '@/constants/colors';
import { Typography } from '@/constants/typography';
import { t } from '@/i18n';
import { OfflineIcon } from '@/components/icons';
import { useAppStore } from '@/stores/app-store';

/**
 * Full-screen overlay shown when the device has no network connectivity.
 * Displays a WiFi-off icon, message, and retry button.
 */
export function OfflineScreen() {
  const setOnlineStatus = useAppStore((s) => s.setOnlineStatus);

  const handleRetry = useCallback(async () => {
    try {
      const state = await NetInfo.fetch();
      setOnlineStatus(state.isConnected ?? false);
    } catch {
      // If NetInfo fails, keep offline state
    }
  }, [setOnlineStatus]);

  return (
    <View style={styles.overlay}>
      <View style={styles.content}>
        <View style={styles.iconContainer}>
          <OfflineIcon size={56} color={Colors.textTertiary} />
        </View>

        <Text style={styles.title}>{t('offline.title')}</Text>
        <Text style={styles.body}>{t('offline.body')}</Text>

        <Pressable
          style={({ pressed }) => [
            styles.retryButton,
            pressed && styles.retryButtonPressed,
          ]}
          onPress={handleRetry}
          accessibilityRole="button"
          accessibilityLabel={t('offline.retry')}
        >
          <Text style={styles.retryButtonText}>{t('offline.retry')}</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  overlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: Colors.surfacePrimary,
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 999,
  },
  content: {
    alignItems: 'center',
    paddingHorizontal: 12,
  },
  iconContainer: {
    marginBottom: 12,
  },
  title: {
    ...Typography.headline.ja,
    color: Colors.textPrimary,
    marginBottom: 12,
  },
  body: {
    ...Typography.body.ja,
    color: Colors.textSecondary,
    textAlign: 'center',
    marginBottom: 20,
  },
  retryButton: {
    backgroundColor: Colors.buttonPrimaryBg,
    paddingHorizontal: 32,
    height: 44,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  retryButtonPressed: {
    opacity: 0.8,
  },
  retryButtonText: {
    ...Typography.body.ja,
    color: Colors.textInverse,
  },
});
