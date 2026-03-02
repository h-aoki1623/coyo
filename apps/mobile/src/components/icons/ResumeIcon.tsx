import Svg, { Path } from 'react-native-svg';

interface Props {
  size?: number;
  color?: string;
}

/**
 * Play triangle icon (filled).
 * Used in the paused conversation banner resume button.
 */
export function ResumeIcon({ size = 22, color = '#FFFFFF' }: Props) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M5 3l14 9-14 9V3Z"
        fill={color}
      />
    </Svg>
  );
}
