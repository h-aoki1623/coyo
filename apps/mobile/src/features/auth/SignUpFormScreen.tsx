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
            <Text style={styles.title}>{t('auth.signUp.title')}</Text>
          </View>

          {/* Form fields */}
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
            accessibilityLabel={t('auth.signUp.submit')}
            testID="signup-submit-button"
          >
            {isLoading ? (
              <ActivityIndicator size="small" color={Colors.textInverse} />
            ) : (
              <Text style={styles.submitButtonText}>{t('auth.signUp.submit')}</Text>
            )}
          </Pressable>
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
});
