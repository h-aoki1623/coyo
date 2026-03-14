import { useState, useCallback } from 'react';
import { View, StyleSheet } from 'react-native';

import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { t } from '@/i18n';
import { useAuthStore } from '@/stores/auth-store';

import { AuthFormLayout } from './components/AuthFormLayout';
import { AuthInput } from './components/AuthInput';
import { ErrorBanner } from './components/ErrorBanner';
import { SubmitButton } from './components/SubmitButton';

import type { AuthStackParamList } from '@/navigation/types';

type Props = NativeStackScreenProps<AuthStackParamList, 'SignUpForm'>;

export function SignUpFormScreen({ navigation }: Props) {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const isLoading = useAuthStore((s) => s.isLoading);
  const error = useAuthStore((s) => s.error);
  const handleSignUpWithEmail = useAuthStore((s) => s.handleSignUpWithEmail);
  const clearError = useAuthStore((s) => s.clearError);

  const isFormValid = name.trim().length > 0
    && email.trim().length > 0
    && password.length > 0;

  const handleSubmit = useCallback(async () => {
    if (!isFormValid || isLoading) return;

    clearError();
    try {
      await handleSignUpWithEmail(email.trim(), password, name.trim());
      navigation.navigate('EmailVerification', { email: email.trim() });
    } catch {
      // Error is set in auth store
    }
  }, [isFormValid, isLoading, email, password, name, handleSignUpWithEmail, navigation, clearError]);

  return (
    <AuthFormLayout
      title={t('auth.signUp.title')}
      onBack={() => navigation.goBack()}
    >
      <View style={styles.form}>
        <AuthInput
          placeholder={t('auth.signUp.name')}
          value={name}
          onChangeText={setName}
          autoCapitalize="none"
          testID="signup-name-input"
        />
        <AuthInput
          placeholder={t('auth.signUp.email')}
          value={email}
          onChangeText={setEmail}
          keyboardType="email-address"
          autoCapitalize="none"
          testID="signup-email-input"
        />
        <AuthInput
          placeholder={t('auth.signUp.password')}
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          testID="signup-password-input"
        />
      </View>

      {error ? <ErrorBanner message={error} /> : null}

      <SubmitButton
        label={t('auth.signUp.submit')}
        onPress={handleSubmit}
        disabled={!isFormValid}
        isLoading={isLoading}
        testID="signup-submit-button"
      />
    </AuthFormLayout>
  );
}

const styles = StyleSheet.create({
  form: {
    gap: 12,
  },
});
