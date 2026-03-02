import Svg, { Path, Line } from 'react-native-svg';

interface Props {
  size?: number;
  color?: string;
}

/**
 * Upward arrow / send icon.
 * Used on the send button in recording controls.
 */
export function SendIcon({ size = 26, color = '#FFFFFF' }: Props) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Line
        x1={12}
        y1={19}
        x2={12}
        y2={5}
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Path
        d="m5 12 7-7 7 7"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}
