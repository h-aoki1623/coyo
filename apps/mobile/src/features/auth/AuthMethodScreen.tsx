import { useState, useCallback } from 'react';
import { useFocusEffect } from '@react-navigation/native';
import {
  View,
  Text,
  Pressable,
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { NavBar } from '@/components/NavBar';
import { Colors } from '@/constants/colors';
import { Typography } from '@/constants/typography';
import { t } from '@/i18n';
import { useAuthStore } from '@/stores/auth-store';

import { AuthProviderButton } from './components/AuthProviderButton';

import type { AuthStackParamList } from '@/navigation/types';

type Props = NativeStackScreenProps<AuthStackParamList, 'AuthMethod'>;

export function AuthMethodScreen({ navigation, route }: Props) {
  const { mode } = route.params;
  const isSignUp = mode === 'signUp';

  const isLoading = useAuthStore((s) => s.isLoading);
  const error = useAuthStore((s) => s.error);
  const clearError = useAuthStore((s) => s.clearError);
  const handleSignInWithGoogle = useAuthStore((s) => s.handleSignInWithGoogle);
  const handleSignInWithApple = useAuthStore((s) => s.handleSignInWithApple);

  const [localLoading, setLocalLoading] = useState(false);

  // Clear stale errors from previous screens when this screen gains focus
  useFocusEffect(
    useCallback(() => {
      clearError();
    }, [clearError]),
  );

  const handleEmailPress = useCallback(() => {
    clearError();
    if (isSignUp) {
      navigation.navigate('SignUpForm');
    } else {
      navigation.navigate('SignInForm');
    }
  }, [isSignUp, navigation, clearError]);

  const handleGooglePress = useCallback(async () => {
    setLocalLoading(true);
    try {
      await handleSignInWithGoogle();
    } catch {
      // Error is set in auth store
    } finally {
      setLocalLoading(false);
    }
  }, [handleSignInWithGoogle]);

  const handleApplePress = useCallback(async () => {
    setLocalLoading(true);
    try {
      await handleSignInWithApple();
    } catch {
      // Error is set in auth store
    } finally {
      setLocalLoading(false);
    }
  }, [handleSignInWithApple]);

  const handleSwitchMode = useCallback(() => {
    clearError();
    navigation.replace('AuthMethod', {
      mode: isSignUp ? 'signIn' : 'signUp',
    });
  }, [isSignUp, navigation, clearError]);

  const title = isSignUp ? t('auth.modal.createAccount') : t('auth.modal.signIn');
  const loading = isLoading || localLoading;

  return (
    <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
      <NavBar onBack={() => navigation.goBack()} />

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        {/* Title */}
        <View style={styles.titleContainer}>
          <Text style={styles.title}>{title}</Text>
        </View>

        {/* Provider buttons */}
        <View style={styles.buttons}>
          <AuthProviderButton
            variant="email"
            label={t('auth.modal.continueWithEmail')}
            onPress={handleEmailPress}
            disabled={loading}
            testID="auth-email-button"
          />
          <AuthProviderButton
            variant="google"
            label={t('auth.modal.continueWithGoogle')}
            onPress={handleGooglePress}
            disabled={loading}
            testID="auth-google-button"
          />
          {Platform.OS === 'ios' ? (
            <AuthProviderButton
              variant="apple"
              label={t('auth.modal.continueWithApple')}
              onPress={handleApplePress}
              disabled={loading}
              testID="auth-apple-button"
            />
          ) : null}
        </View>

        {/* Loading indicator */}
        {loading ? (
          <ActivityIndicator
            size="small"
            color={Colors.buttonPrimaryBg}
            style={styles.loader}
          />
        ) : null}

        {/* Error message */}
        {error ? (
          <View style={styles.errorContainer}>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        ) : null}

        {/* Terms text (sign-up only) */}
        {isSignUp ? (
          <Text style={styles.terms}>
            {t('auth.modal.termsPrefix')}
            <Text style={styles.termsLink}>{t('auth.modal.termsOfService')}</Text>
            {t('auth.modal.termsConnector')}
            <Text style={styles.termsLink}>{t('auth.modal.privacyPolicy')}</Text>
            {t('auth.modal.termsSuffix')}
          </Text>
        ) : null}

        {/* Switch mode link */}
        <View style={styles.switchContainer}>
          <Text style={styles.switchText}>
            {isSignUp
              ? t('auth.modal.hasAccountPrompt')
              : t('auth.modal.noAccountPrompt')}
          </Text>
          <Pressable
            onPress={handleSwitchMode}
            hitSlop={8}
            accessibilityRole="button"
            accessibilityLabel={isSignUp ? t('auth.modal.signIn') : t('auth.modal.signUp')}
            testID="auth-switch-mode"
          >
            <Text style={styles.switchLink}>
              {isSignUp ? t('auth.modal.signIn') : t('auth.modal.signUp')}
            </Text>
          </Pressable>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.surfaceCard,
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingTop: 32,
    paddingBottom: 32,
  },
  titleContainer: {
    paddingBottom: 24,
  },
  title: {
    ...Typography.title.ja,
    color: Colors.textPrimary,
    textAlign: 'center',
  },
  buttons: {
    gap: 12,
  },
  loader: {
    marginTop: 20,
  },
  errorContainer: {
    marginTop: 16,
    backgroundColor: Colors.statusErrorBg,
    borderRadius: 10,
    padding: 12,
  },
  errorText: {
    ...Typography.caption.ja,
    color: Colors.statusError,
    textAlign: 'center',
  },
  terms: {
    ...Typography.caption.ja,
    color: Colors.textTertiary,
    textAlign: 'center',
    marginTop: 24,
  },
  termsLink: {
    color: Colors.buttonPrimaryBg,
  },
  switchContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 24,
    flexWrap: 'wrap',
  },
  switchText: {
    ...Typography.caption.ja,
    color: Colors.textTertiary,
  },
  switchLink: {
    ...Typography.caption.ja,
    color: Colors.buttonPrimaryBg,
  },
});
