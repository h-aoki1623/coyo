import { t } from '@/i18n';
import { Colors } from '@/constants/colors';
import type { TopicKey } from '@/navigation/types';

export interface Topic {
  key: TopicKey;
  label: string;
  icon: 'globe' | 'briefcase' | 'building' | 'monitor' | 'film';
  iconBg: string;
  iconColor: string;
}

/**
 * Returns the list of topics with localized labels.
 * Called as a function so it picks up the current locale at render time.
 */
export function getTopics(): Topic[] {
  return [
    { key: 'sports', label: t('topics.sports'), icon: 'globe', iconBg: Colors.topicSportsBg, iconColor: Colors.topicSports },
    { key: 'business', label: t('topics.business'), icon: 'briefcase', iconBg: Colors.topicBusinessBg, iconColor: Colors.topicBusiness },
    { key: 'politics', label: t('topics.politics'), icon: 'building', iconBg: Colors.topicPoliticsBg, iconColor: Colors.topicPolitics },
    { key: 'technology', label: t('topics.technology'), icon: 'monitor', iconBg: Colors.topicTechnologyBg, iconColor: Colors.topicTechnology },
    { key: 'entertainment', label: t('topics.entertainment'), icon: 'film', iconBg: Colors.topicEntertainmentBg, iconColor: Colors.topicEntertainment },
  ];
}

/**
 * Static topic data (without labels) for lookups that don't need localization.
 */
const TOPIC_META: Record<TopicKey, Omit<Topic, 'label'>> = {
  sports: { key: 'sports', icon: 'globe', iconBg: Colors.topicSportsBg, iconColor: Colors.topicSports },
  business: { key: 'business', icon: 'briefcase', iconBg: Colors.topicBusinessBg, iconColor: Colors.topicBusiness },
  politics: { key: 'politics', icon: 'building', iconBg: Colors.topicPoliticsBg, iconColor: Colors.topicPolitics },
  technology: { key: 'technology', icon: 'monitor', iconBg: Colors.topicTechnologyBg, iconColor: Colors.topicTechnology },
  entertainment: { key: 'entertainment', icon: 'film', iconBg: Colors.topicEntertainmentBg, iconColor: Colors.topicEntertainment },
};

/**
 * Find a topic by its key with localized label. Returns undefined if not found.
 */
export function findTopic(key: string): Topic | undefined {
  const meta = TOPIC_META[key as TopicKey];
  if (!meta) return undefined;
  return { ...meta, label: t(`topics.${key}`) };
}
