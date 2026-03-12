import { useState, useCallback } from 'react';
import {
  View,
  Text,
  Pressable,
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { NavBar } from '@/components/NavBar';
import { Colors } from '@/constants/colors';
import { Typography } from '@/constants/typography';
import { t } from '@/i18n';
import { useAuthStore } from '@/stores/auth-store';

import { AuthInput } from './components/AuthInput';

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
    <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
      <NavBar onBack={() => navigation.goBack()} />

      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <ScrollView
          style={styles.flex}
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
        >
          {/* Title */}
          <View style={styles.titleContainer}>
            <Text style={styles.title}>{t('auth.signIn.title')}</Text>
          </View>

          {/* Form fields */}
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

          {/* Error message */}
          {error ? (
            <View style={styles.errorContainer}>
              <Text style={styles.errorText}>{error}</Text>
            </View>
          ) : null}

          {/* Submit button */}
          <Pressable
            style={({ pressed }) => [
              styles.submitButton,
              (!isFormValid || isLoading) && styles.submitButtonDisabled,
              pressed && isFormValid && styles.submitButtonPressed,
            ]}
            onPress={handleSubmit}
            disabled={!isFormValid || isLoading}
            accessibilityRole="button"
            accessibilityLabel={t('auth.signIn.submit')}
            testID="signin-submit-button"
          >
            {isLoading ? (
              <ActivityIndicator size="small" color={Colors.textInverse} />
            ) : (
              <Text style={styles.submitButtonText}>{t('auth.signIn.submit')}</Text>
            )}
          </Pressable>

          {/* Forgot password */}
          <View style={styles.forgotContainer}>
            <Text style={styles.forgotText}>{t('auth.signIn.forgotPassword')}</Text>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

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
  form: {
    gap: 12,
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
  submitButton: {
    backgroundColor: Colors.buttonPrimaryBg,
    height: 48,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 20,
  },
  submitButtonDisabled: {
    opacity: 0.5,
  },
  submitButtonPressed: {
    opacity: 0.8,
  },
  submitButtonText: {
    ...Typography.body.ja,
    color: Colors.textInverse,
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
