import { useCallback, useEffect } from 'react';
import { BackHandler, View, Text, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { CheckIcon } from '@/components/icons';
import { Colors } from '@/constants/colors';
import { Typography } from '@/constants/typography';
import { t } from '@/i18n';

import { SubmitButton } from './components/SubmitButton';

import type { AuthStackParamList } from '@/navigation/types';

type Props = NativeStackScreenProps<AuthStackParamList, 'PasswordResetSuccess'>;

export function PasswordResetSuccessScreen({ navigation }: Props) {
  const handleBack = useCallback(() => {
    navigation.reset({ index: 0, routes: [{ name: 'Welcome' }] });
  }, [navigation]);

  // Android hardware back would otherwise pop to PasswordResetNewPassword,
  // whose oobCode has been consumed — route back to Welcome instead.
  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      handleBack();
      return true;
    });
    return () => sub.remove();
  }, [handleBack]);

  return (
    <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
      <View style={styles.content}>
        <View style={styles.iconRow}>
          <View style={styles.iconBox}>
            <CheckIcon size={38} color={Colors.statusSuccess} />
          </View>
        </View>

        <Text style={styles.title}>{t('auth.passwordReset.success.title')}</Text>
        <Text style={styles.description}>
          {t('auth.passwordReset.success.description')}
        </Text>
      </View>

      <View style={styles.footer}>
        <SubmitButton
          label={t('auth.passwordReset.success.backToSignIn')}
          onPress={handleBack}
          testID="password-reset-success-back"
        />
      </View>
    </SafeAreaView>
  );
}

const ICON_BOX_SIZE = 72;

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.surfaceCard,
  },
  content: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 20,
  },
  iconRow: {
    marginBottom: 24,
  },
  iconBox: {
    width: ICON_BOX_SIZE,
    height: ICON_BOX_SIZE,
    borderRadius: 20,
    backgroundColor: Colors.statusSuccessBg,
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: {
    ...Typography.title.ja,
    color: Colors.textPrimary,
    textAlign: 'center',
    marginBottom: 12,
  },
  description: {
    ...Typography.body.ja,
    color: Colors.textSecondary,
    textAlign: 'center',
  },
  footer: {
    paddingHorizontal: 20,
    paddingBottom: 20,
  },
});
