import { View, Text, Pressable, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { LogoIcon } from '@/components/icons';
import { Colors } from '@/constants/colors';
import { Typography } from '@/constants/typography';
import { t } from '@/i18n';

import type { AuthStackParamList } from '@/navigation/types';

type Props = NativeStackScreenProps<AuthStackParamList, 'Welcome'>;

export function WelcomeScreen({ navigation }: Props) {
  const handleSignIn = () => {
    navigation.navigate('AuthMethod', { mode: 'signIn' });
  };

  const handleGetStarted = () => {
    navigation.navigate('AuthMethod', { mode: 'signUp' });
  };

  return (
    <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
      {/* Header with sign-in link */}
      <View style={styles.header}>
        <View style={styles.headerSpacer} />
        <Pressable
          onPress={handleSignIn}
          hitSlop={8}
          accessibilityRole="button"
          accessibilityLabel={t('auth.welcome.signIn')}
          testID="welcome-sign-in"
        >
          <Text style={styles.signInLink}>{t('auth.welcome.signIn')}</Text>
        </Pressable>
      </View>

      {/* Body */}
      <View style={styles.body}>
        <View style={styles.logoWrapper}>
          <LogoIcon width={48} height={24} color={Colors.buttonPrimaryBg} />
        </View>
        <View style={styles.headlineWrapper}>
          <Text style={styles.headline}>
            {t('auth.welcome.headline')}
          </Text>
        </View>
        <Text style={styles.subtitle}>
          {t('auth.welcome.subtitle')}
        </Text>
      </View>

      {/* Footer */}
      <View style={styles.footer}>
        <Pressable
          style={({ pressed }) => [
            styles.ctaButton,
            pressed && styles.ctaButtonPressed,
          ]}
          onPress={handleGetStarted}
          accessibilityRole="button"
          accessibilityLabel={t('auth.welcome.getStarted')}
          testID="welcome-get-started"
        >
          <Text style={styles.ctaButtonText}>{t('auth.welcome.getStarted')}</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.surfacePrimary,
    paddingHorizontal: 20,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    alignItems: 'center',
    height: 56,
  },
  headerSpacer: {
    flex: 1,
  },
  signInLink: {
    ...Typography.body.ja,
    color: Colors.buttonPrimaryBg,
  },
  body: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'flex-start',
  },
  logoWrapper: {
    marginBottom: 24,
  },
  headlineWrapper: {
    marginBottom: 12,
  },
  headline: {
    ...Typography.display.ja,
    color: Colors.textPrimary,
    lineHeight: 42,
  },
  subtitle: {
    ...Typography.body.ja,
    color: Colors.textSecondary,
  },
  footer: {
    paddingBottom: 32,
  },
  ctaButton: {
    backgroundColor: Colors.buttonPrimaryBg,
    height: 48,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  ctaButtonPressed: {
    opacity: 0.8,
  },
  ctaButtonText: {
    ...Typography.body.ja,
    color: Colors.textInverse,
  },
});
