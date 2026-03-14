import { useState, useCallback } from 'react';
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

import type { AuthStackParamList } from '@/navigation/types';

type Props = NativeStackScreenProps<AuthStackParamList, 'SignInForm'>;

export function SignInFormScreen({ navigation }: Props) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const isLoading = useAuthStore((s) => s.isLoading);
  const error = useAuthStore((s) => s.error);
  const handleSignInWithEmail = useAuthStore((s) => s.handleSignInWithEmail);
  const clearError = useAuthStore((s) => s.clearError);

  const isFormValid = email.trim().length > 0 && password.length > 0;

  const handleSubmit = useCallback(async () => {
    if (!isFormValid || isLoading) return;

    clearError();
    try {
      await handleSignInWithEmail(email.trim(), password);

      // After sign-in, check if email is verified
      // The auth store listener will update isEmailVerified
      // If not verified, navigate to the verification screen
      const currentVerified = useAuthStore.getState().isEmailVerified;
      if (!currentVerified) {
        navigation.navigate('EmailVerification', { email: email.trim() });
      }
      // If verified, the RootNavigator auth gate will redirect to the main app
    } catch {
      // Error is set in auth store
    }
  }, [isFormValid, isLoading, email, password, handleSignInWithEmail, navigation, clearError]);

  return (
    <AuthFormLayout
      title={t('auth.signIn.title')}
      onBack={() => navigation.goBack()}
    >
      <View style={styles.form}>
        <AuthInput
          placeholder={t('auth.signIn.email')}
          value={email}
          onChangeText={setEmail}
          keyboardType="email-address"
          autoCapitalize="none"
          testID="signin-email-input"
        />
        <AuthInput
          placeholder={t('auth.signIn.password')}
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          testID="signin-password-input"
        />
      </View>

      {error ? <ErrorBanner message={error} /> : null}

      <SubmitButton
        label={t('auth.signIn.submit')}
        onPress={handleSubmit}
        disabled={!isFormValid}
        isLoading={isLoading}
        testID="signin-submit-button"
      />

      <View style={styles.forgotContainer}>
        <Text style={styles.forgotText}>{t('auth.signIn.forgotPassword')}</Text>
      </View>
    </AuthFormLayout>
  );
}

const styles = StyleSheet.create({
  form: {
    gap: 12,
  },
  forgotContainer: {
    marginTop: 20,
    alignItems: 'center',
  },
  forgotText: {
    ...Typography.caption.ja,
    color: Colors.buttonPrimaryBg,
  },
});
