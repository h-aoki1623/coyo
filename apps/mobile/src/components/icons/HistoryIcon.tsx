import Svg, { Circle, Path } from 'react-native-svg';

interface Props {
  size?: number;
  color?: string;
}

/**
 * Clock / history icon.
 * Used in the Home screen header to navigate to conversation history.
 */
export function HistoryIcon({ size = 20, color = '#1E293B' }: Props) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Circle
        cx={12}
        cy={12}
        r={10}
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Clock hands: hour and minute */}
      <Path
        d="M12 6v6l4 2"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}
