import { View, Text, StyleSheet } from 'react-native';
import { TrophyIcon, CotoAvatar } from '@/components/icons';
import { Colors } from '@/constants/colors';
import { Fonts, Typography } from '@/constants/typography';
import { t } from '@/i18n';

export function EmptyFeedbackState() {
  return (
    <View style={styles.container}>
      <View style={styles.iconContainer}>
        <TrophyIcon size={38} color="#16A34A" />
      </View>
      <Text style={styles.title}>{t('emptyFeedback.title')}</Text>
      <View style={styles.praiseCard}>
        <CotoAvatar size={32} />
        <View style={styles.praiseCardContent}>
          <Text style={styles.praiseCardTitle}>{t('emptyFeedback.messageFrom')}</Text>
          <Text style={styles.praiseCardBody}>{t('emptyFeedback.body')}</Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
  },
  iconContainer: {
    width: 80,
    height: 80,
    borderRadius: 24,
    backgroundColor: Colors.statusSuccessBg,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 20,
  },
  title: {
    ...Typography.title.ja,
    color: Colors.textPrimary,
    letterSpacing: -0.3,
    textAlign: 'center',
    marginBottom: 12,
  },
  praiseCard: {
    flexDirection: 'row',
    backgroundColor: Colors.surfaceCard,
    borderWidth: 1,
    borderColor: Colors.borderSubtle,
    borderRadius: 14,
    padding: 17,
    gap: 12,
    width: '100%',
  },
  praiseCardContent: {
    flex: 1,
    gap: 8,
  },
  praiseCardTitle: {
    ...Typography.bodySmall.ja,
    fontFamily: Fonts.notoSansJP.bold,
    color: Colors.buttonPrimaryBg,
  },
  praiseCardBody: {
    ...Typography.caption.ja,
    color: Colors.textSecondary,
  },
});
