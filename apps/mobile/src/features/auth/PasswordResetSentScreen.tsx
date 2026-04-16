import { useState, useCallback, useRef, useEffect } from 'react';
import { View, Text, Pressable, ScrollView, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { MailIcon } from '@/components/icons';
import { NavBar } from '@/components/NavBar';
import { Colors } from '@/constants/colors';
import { Typography } from '@/constants/typography';
import { t } from '@/i18n';
import { useAuthStore } from '@/stores/auth-store';

import { EmailCard } from './components/EmailCard';
import { StepItem } from './components/StepItem';

import type { AuthStackParamList } from '@/navigation/types';

type Props = NativeStackScreenProps<AuthStackParamList, 'PasswordResetSent'>;

const RESEND_COOLDOWN_SECONDS = 60;

export function PasswordResetSentScreen({ route, navigation }: Props) {
  const { email } = route.params;
  const requestPasswordReset = useAuthStore((s) => s.requestPasswordReset);

  const [cooldownRemaining, setCooldownRemaining] = useState(0);
  const [isResending, setIsResending] = useState(false);
  const cooldownTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      if (cooldownTimerRef.current) {
        clearInterval(cooldownTimerRef.current);
      }
    };
  }, []);

  const startCooldown = useCallback(() => {
    setCooldownRemaining(RESEND_COOLDOWN_SECONDS);
    if (cooldownTimerRef.current) {
      clearInterval(cooldownTimerRef.current);
    }
    cooldownTimerRef.current = setInterval(() => {
      setCooldownRemaining((prev) => {
        if (prev <= 1) {
          if (cooldownTimerRef.current) {
            clearInterval(cooldownTimerRef.current);
            cooldownTimerRef.current = null;
          }
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  }, []);

  const handleResend = useCallback(async () => {
    if (cooldownRemaining > 0 || isResending) return;

    setIsResending(true);
    try {
      await requestPasswordReset(email);
      startCooldown();
    } catch {
      // Error handled in auth store
    } finally {
      setIsResending(false);
    }
  }, [cooldownRemaining, isResending, requestPasswordReset, email, startCooldown]);

  const handleBack = useCallback(() => {
    navigation.goBack();
  }, [navigation]);

  return (
    <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
      <NavBar onBack={handleBack} />

      <ScrollView
        style={styles.flex}
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={styles.title}>{t('auth.passwordReset.sent.title')}</Text>

        <View style={styles.iconRow}>
          <View style={styles.mailIconCircle}>
            <MailIcon size={32} color={Colors.buttonPrimaryBg} />
          </View>
        </View>

        <Text style={styles.description}>
          {t('auth.passwordReset.sent.description')}
        </Text>

        <View style={styles.emailCardWrapper}>
          <EmailCard email={email} />
        </View>

        <View style={styles.steps}>
          <StepItem number={1} text={t('auth.passwordReset.sent.step1')} />
          <StepItem number={2} text={t('auth.passwordReset.sent.step2')} />
          <StepItem number={3} text={t('auth.passwordReset.sent.step3')} />
        </View>

        <View style={styles.resendRow}>
          <Text style={styles.resendLabel}>{t('auth.passwordReset.sent.didNotReceive')}</Text>
          <Pressable
            onPress={handleResend}
            disabled={cooldownRemaining > 0 || isResending}
            hitSlop={8}
            accessibilityRole="button"
            accessibilityLabel={t('auth.passwordReset.sent.resend')}
            testID="password-reset-sent-resend"
          >
            <Text
              style={[
                styles.resendLink,
                cooldownRemaining > 0 && styles.resendLinkDisabled,
              ]}
            >
              {cooldownRemaining > 0
                ? t('auth.passwordReset.sent.resendCooldown', { seconds: cooldownRemaining })
                : t('auth.passwordReset.sent.resend')}
            </Text>
          </Pressable>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const MAIL_ICON_SIZE = 72;

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.surfaceCard,
  },
  flex: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 32,
    alignItems: 'center',
  },
  title: {
    ...Typography.title.ja,
    color: Colors.textPrimary,
    textAlign: 'center',
    marginBottom: 24,
  },
  iconRow: {
    marginBottom: 24,
  },
  mailIconCircle: {
    width: MAIL_ICON_SIZE,
    height: MAIL_ICON_SIZE,
    borderRadius: 20,
    backgroundColor: Colors.accentBg,
    borderWidth: 1,
    borderColor: Colors.accentBorder,
    alignItems: 'center',
    justifyContent: 'center',
  },
  description: {
    ...Typography.body.ja,
    color: Colors.textSecondary,
    textAlign: 'center',
    marginBottom: 20,
  },
  emailCardWrapper: {
    width: '100%',
    marginBottom: 24,
  },
  steps: {
    width: '100%',
    gap: 12,
  },
  resendRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 24,
  },
  resendLabel: {
    ...Typography.caption.ja,
    color: Colors.textTertiary,
  },
  resendLink: {
    ...Typography.caption.ja,
    color: Colors.buttonPrimaryBg,
  },
  resendLinkDisabled: {
    color: Colors.textTertiary,
  },
});
