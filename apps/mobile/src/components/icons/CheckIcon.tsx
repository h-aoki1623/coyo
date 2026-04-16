import Svg, { Path } from 'react-native-svg';

import { Colors } from '@/constants/colors';

interface Props {
  size?: number;
  color?: string;
  strokeWidth?: number;
}

/**
 * Simple stroke-only checkmark (no enclosing circle).
 * Used on the password reset success screen.
 */
export function CheckIcon({ size = 24, color = Colors.statusSuccess, strokeWidth = 3 }: Props) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M5 12.5L10 17.5L19 7.5"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}
