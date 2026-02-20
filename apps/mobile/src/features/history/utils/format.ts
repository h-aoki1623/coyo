/**
 * Formatting utilities for history screens.
 * Extracted from HistoryListScreen and HistoryDetailScreen for testability.
 */

export function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds === 0) return '--';
  const mins = Math.floor(seconds / 60);
  if (mins === 0) return '1\u5206\u672A\u6E80';
  return `${mins}\u5206\u9593`;
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

  if (diffDays === 0) return '\u4ECA\u65E5';
  if (diffDays === 1) return '\u6628\u65E5';

  return `${date.getMonth() + 1}\u6708${date.getDate()}\u65E5`;
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
  if (diffDays === 0) datePart = '\u4ECA\u65E5';
  else if (diffDays === 1) datePart = '\u6628\u65E5';
  else datePart = `${date.getMonth() + 1}\u6708${date.getDate()}\u65E5`;

  const hours = date.getHours();
  const minutes = date.getMinutes().toString().padStart(2, '0');
  const ampm = hours >= 12 ? 'PM' : 'AM';
  const displayHour = hours % 12 || 12;
  const timePart = `${displayHour}:${minutes} ${ampm}`;

  const durationPart = formatDuration(durationSeconds);

  return `${datePart} ${timePart} \u00B7 ${durationPart}`;
}
