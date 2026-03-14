import { View, Text, StyleSheet } from 'react-native';

import { MailIcon } from '@/components/icons';
import { Colors } from '@/constants/colors';
import { Typography } from '@/constants/typography';
import { t } from '@/i18n';

interface Props {
  email: string;
}

export function EmailCard({ email }: Props) {
  return (
    <View style={styles.container}>
      <View style={styles.iconWrapper}>
        <MailIcon size={18} color={Colors.buttonPrimaryBg} />
      </View>
      <View style={styles.textContainer}>
        <Text style={styles.email} numberOfLines={1}>{email}</Text>
        <Text style={styles.suffix}>{t('auth.verification.sentTo')}</Text>
      </View>
    </View>
  );
}

const ICON_SIZE = 34;

const styles = StyleSheet.create({
  container: {
    backgroundColor: Colors.surfaceElevated,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  iconWrapper: {
    width: ICON_SIZE,
    height: ICON_SIZE,
    borderRadius: 10,
    backgroundColor: Colors.accentIconBg,
    alignItems: 'center',
    justifyContent: 'center',
  },
  textContainer: {
    flex: 1,
  },
  email: {
    ...Typography.caption.ja,
    color: Colors.textPrimary,
  },
  suffix: {
    ...Typography.caption.ja,
    color: Colors.textSecondary,
  },
});
