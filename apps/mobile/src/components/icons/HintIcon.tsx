import Svg, { Path } from 'react-native-svg';

interface Props {
  size?: number;
  color?: string;
}

/**
 * Diamond / sparkle hint icon.
 * Small indicator used in correction explanations.
 */
export function HintIcon({ size = 11, color = '#94A3B8' }: Props) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      {/* Four-pointed sparkle / diamond shape */}
      <Path
        d="M12 2L14.5 9.5L22 12L14.5 14.5L12 22L9.5 14.5L2 12L9.5 9.5L12 2Z"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}
