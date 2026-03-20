const BADGE_PALETTE = [
  { bg: '#DBEAFE', text: '#1E40AF' },  // blue
  { bg: '#DCFCE7', text: '#166534' },  // green
  { bg: '#EDE9FE', text: '#5B21B6' },  // purple
  { bg: '#FEE2E2', text: '#991B1B' },  // red
  { bg: '#FEF3C7', text: '#92400E' },  // amber
  { bg: '#FCE7F3', text: '#9D174D' },  // pink
  { bg: '#FFEDD5', text: '#9A3412' },  // orange
] as const;

export function getBadgeColor(keyword: string): { bg: string; text: string } {
  let hash = 0;
  for (let i = 0; i < keyword.length; i++) {
    hash = keyword.charCodeAt(i) + ((hash << 5) - hash);
  }
  const index = Math.abs(hash) % BADGE_PALETTE.length;
  return BADGE_PALETTE[index];
}
