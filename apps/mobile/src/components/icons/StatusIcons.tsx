import Svg, { Circle, Path, Rect } from 'react-native-svg';

interface IconProps {
  size?: number;
  color?: string;
}

/**
 * Check circle icon for "no corrections" / clean status.
 * Filled green circle with a small checkmark inside.
 */
export function CheckCircleIcon({ size = 16, color = '#22C55E' }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 16 16" fill="none">
      <Rect width="16" height="16" rx="8" fill="#DCFCE7" />
      <Path
        d="M4.75 8.5L7 10.75L11.25 5.5"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

/**
 * Exclamation circle icon for corrections / warning status.
 * Filled yellow circle with a small exclamation mark inside.
 */
export function ExclamationCircleIcon({ size = 16, color = '#F59E0B' }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 16 16" fill="none">
      <Rect width="16" height="16" rx="8" fill="#FEF3C7" />
      <Path
        d="M8 4.5v4.5"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
      />
      <Circle cx={8} cy={11.25} r={0.75} fill={color} />
    </Svg>
  );
}

/**
 * Chevron-down icon for collapsed/expanded state toggle.
 * Small downward-pointing angle bracket.
 */
export function ChevronDownIcon({ size = 16, color = '#64748B' }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="m6 9 6 6 6-6"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

/**
 * Chevron-right icon for collapsed state indicator.
 * Small right-pointing angle bracket.
 */
export function ChevronRightIcon({ size = 16, color = '#64748B' }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="m9 18 6-6-6-6"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}
