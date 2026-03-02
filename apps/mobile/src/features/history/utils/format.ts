/**
 * Formatting utilities for history screens.
 * All user-facing strings use i18n for localization.
 */
import { t } from '@/i18n';

export function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds === 0) return t('duration.none');
  const mins = Math.floor(seconds / 60);
  if (mins === 0) return t('duration.lessThanMinute');
  return t('duration.minutes', { mins });
}

export function formatTime(isoString: string): string {
  const date = new Date(isoString);
  const hours = date.getHours();
  const minutes = date.getMinutes().toString().padStart(2, '0');
  const ampm = hours >= 12 ? 'PM' : 'AM';
  const displayHour = hours % 12 || 12;
  return `${displayHour}:${minutes} ${ampm}`;
}

export function getSectionTitle(isoString: string, now?: Date): string {
  const date = new Date(isoString);
  const reference = now ?? new Date();

  const dateDay = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const today = new Date(reference.getFullYear(), reference.getMonth(), reference.getDate());
  const diffDays = Math.floor((today.getTime() - dateDay.getTime()) / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return t('dates.today');
  if (diffDays === 1) return t('dates.yesterday');

  return t('dates.dateFormat', { month: date.getMonth() + 1, day: date.getDate() });
}

export interface SectionData<T> {
  title: string;
  data: T[];
}

export function groupByDate<T extends { startedAt: string }>(
  items: T[],
  now?: Date,
): SectionData<T>[] {
  const sections: Map<string, T[]> = new Map();

  for (const item of items) {
    const title = getSectionTitle(item.startedAt, now);
    const existing = sections.get(title);
    if (existing) {
      existing.push(item);
    } else {
      sections.set(title, [item]);
    }
  }

  return Array.from(sections.entries()).map(([title, data]) => ({
    title,
    data,
  }));
}

export function formatDetailHeader(
  isoString: string,
  durationSeconds: number | null,
  now?: Date,
): string {
  const date = new Date(isoString);
  const reference = now ?? new Date();

  const dateDay = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const today = new Date(reference.getFullYear(), reference.getMonth(), reference.getDate());
  const diffDays = Math.floor((today.getTime() - dateDay.getTime()) / (1000 * 60 * 60 * 24));

  let datePart: string;
  if (diffDays === 0) datePart = t('dates.today');
  else if (diffDays === 1) datePart = t('dates.yesterday');
  else datePart = t('dates.dateFormat', { month: date.getMonth() + 1, day: date.getDate() });

  const hours = date.getHours();
  const minutes = date.getMinutes().toString().padStart(2, '0');
  const ampm = hours >= 12 ? 'PM' : 'AM';
  const displayHour = hours % 12 || 12;
  const timePart = `${displayHour}:${minutes} ${ampm}`;

  const durationPart = formatDuration(durationSeconds);

  return `${datePart} ${timePart} \u00B7 ${durationPart}`;
}
