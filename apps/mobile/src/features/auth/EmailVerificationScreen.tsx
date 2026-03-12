import { useState, useCallback, useRef, useEffect } from 'react';
import {
  View,
  Text,
  Pressable,
  ScrollView,
  StyleSheet,
  AppState,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { MailIcon } from '@/components/icons';
import { Colors } from '@/constants/colors';
import { Typography } from '@/constants/typography';
import { t } from '@/i18n';
import { useAuthStore } from '@/stores/auth-store';

import { EmailCard } from './components/EmailCard';
import { StepItem } from './components/StepItem';

import type { AuthStackParamList } from '@/navigation/types';

type Props = NativeStackScreenProps<AuthStackParamList, 'EmailVerification'> | Record<string, never>;

const RESEND_COOLDOWN_SECONDS = 60;

export function EmailVerificationScreen(props: Props) {
  // Get email from route params or from the auth store user
  const user = useAuthStore((s) => s.user);
  const checkEmailVerified = useAuthStore((s) => s.checkEmailVerified);
  const resendVerification = useAuthStore((s) => s.resendVerification);
  const handleSignOut = useAuthStore((s) => s.handleSignOut);

  const email = ('route' in props && props.route?.params?.email)
    ? props.route.params.email
    : user?.email ?? '';

  const [cooldownRemaining, setCooldownRemaining] = useState(0);
  const [isResending, setIsResending] = useState(false);
  const cooldownTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Auto-check verification when app returns to foreground (e.g. after
  // the user taps the verification link in their email and switches back).
  useEffect(() => {
    const subscription = AppState.addEventListener('change', (nextState) => {
      if (nextState === 'active') {
        checkEmailVerified();
      }
    });
    return () => subscription.remove();
  }, [checkEmailVerified]);

  // Cleanup timer on unmount
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
      await resendVerification();
      startCooldown();
    } catch {
      // Error handled in auth store
    } finally {
      setIsResending(false);
    }
  }, [cooldownRemaining, isResending, resendVerification, startCooldown]);

  return (
    <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
      {/* Header — no back button */}
      <View style={styles.header}>
        <View style={styles.headerSpacer} />
        <Text style={styles.headerTitle}>{t('auth.verification.title')}</Text>
        <View style={styles.headerSpacer} />
      </View>

      <ScrollView
        style={styles.flex}
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        {/* Mail icon */}
        <View style={styles.iconRow}>
          <View style={styles.mailIconCircle}>
            <MailIcon size={32} color={Colors.buttonPrimaryBg} />
          </View>
        </View>

        {/* Description */}
        <Text style={styles.description}>
          {t('auth.verification.description')}
        </Text>

        {/* Email card */}
        <View style={styles.emailCardWrapper}>
          <EmailCard email={email} />
        </View>

        {/* Steps */}
        <View style={styles.steps}>
          <StepItem number={1} text={t('auth.verification.step1')} />
          <StepItem
            number={2}
            text={t('auth.verification.step2')}
          />
          <StepItem
            number={3}
            text={t('auth.verification.step3')}
          />
        </View>

        {/* Resend link */}
        <View style={styles.resendRow}>
          <Text style={styles.resendLabel}>{t('auth.verification.didNotReceive')}</Text>
          <Pressable
            onPress={handleResend}
            disabled={cooldownRemaining > 0 || isResending}
            hitSlop={8}
            accessibilityRole="button"
            accessibilityLabel={t('auth.verification.resend')}
            testID="email-verification-resend"
          >
            <Text
              style={[
                styles.resendLink,
                cooldownRemaining > 0 && styles.resendLinkDisabled,
              ]}
            >
              {cooldownRemaining > 0
                ? t('auth.verification.resendCooldown', { seconds: cooldownRemaining })
                : t('auth.verification.resend')}
            </Text>
          </Pressable>
        </View>

        {/* Sign out */}
        <Pressable
          onPress={handleSignOut}
          hitSlop={8}
          accessibilityRole="button"
          accessibilityLabel={t('auth.signOut')}
          testID="email-verification-sign-out"
        >
          <Text style={styles.signOutLink}>{t('auth.signOut')}</Text>
        </Pressable>
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
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    height: 56,
    paddingHorizontal: 20,
  },
  headerSpacer: {
    width: 40,
    height: 40,
  },
  headerTitle: {
    ...Typography.title.ja,
    color: Colors.textPrimary,
    textAlign: 'center',
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 32,
    alignItems: 'center',
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
  signOutLink: {
    ...Typography.body.ja,
    color: Colors.statusError,
    marginTop: 24,
  },
});
