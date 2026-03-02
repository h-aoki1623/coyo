import Svg, { Line } from 'react-native-svg';

interface Props {
  size?: number;
  color?: string;
}

/**
 * X / close icon.
 * Used on the cancel button in recording controls and dismissable elements.
 */
export function CloseIcon({ size = 18, color = '#64748B' }: Props) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Line
        x1={18}
        y1={6}
        x2={6}
        y2={18}
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Line
        x1={6}
        y1={6}
        x2={18}
        y2={18}
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}
