import { useState, useCallback, useEffect } from 'react';
import { View, Text, StyleSheet } from 'react-native';

import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { Colors } from '@/constants/colors';
import { Typography } from '@/constants/typography';
import { t } from '@/i18n';
import { useAuthStore } from '@/stores/auth-store';

import { AuthFormLayout } from './components/AuthFormLayout';
import { AuthInput } from './components/AuthInput';
import { ErrorBanner } from './components/ErrorBanner';
import { SubmitButton } from './components/SubmitButton';
import { isEmailValid } from './validation';

import type { AuthStackParamList } from '@/navigation/types';

type Props = NativeStackScreenProps<AuthStackParamList, 'PasswordResetEmail'>;

export function PasswordResetEmailScreen({ navigation }: Props) {
  const [email, setEmail] = useState('');

  const isLoading = useAuthStore((s) => s.isLoading);
  const error = useAuthStore((s) => s.error);
  const requestPasswordReset = useAuthStore((s) => s.requestPasswordReset);
  const clearError = useAuthStore((s) => s.clearError);

  // Clear any leftover error when the screen mounts.
  useEffect(() => {
    clearError();
  }, [clearError]);

  const trimmed = email.trim();
  const isFormValid = isEmailValid(trimmed);

  const handleSubmit = useCallback(async () => {
    if (!isFormValid || isLoading) return;

    clearError();
    try {
      await requestPasswordReset(trimmed);
      navigation.navigate('PasswordResetSent', { email: trimmed });
    } catch {
      // Error surfaced via the auth store
    }
  }, [isFormValid, isLoading, trimmed, requestPasswordReset, navigation, clearError]);

  return (
    <AuthFormLayout
      title={t('auth.passwordReset.enterEmail.title')}
      onBack={() => navigation.goBack()}
    >
      <Text style={styles.description}>
        {t('auth.passwordReset.enterEmail.description')}
      </Text>

      <View style={styles.form}>
        <AuthInput
          placeholder={t('auth.passwordReset.enterEmail.placeholder')}
          value={email}
          onChangeText={setEmail}
          keyboardType="email-address"
          autoCapitalize="none"
          testID="password-reset-email-input"
        />
      </View>

      {error ? <ErrorBanner message={error} /> : null}

      <SubmitButton
        label={t('auth.passwordReset.enterEmail.submit')}
        onPress={handleSubmit}
        disabled={!isFormValid}
        isLoading={isLoading}
        testID="password-reset-email-submit"
      />
    </AuthFormLayout>
  );
}

const styles = StyleSheet.create({
  description: {
    ...Typography.body.ja,
    color: Colors.textSecondary,
    textAlign: 'center',
    marginBottom: 20,
  },
  form: {
    gap: 12,
  },
});
