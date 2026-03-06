import Svg, { Circle, G, Path } from 'react-native-svg';

interface Props {
  /** Diameter of the avatar circle in pixels. */
  size?: number;
  /**
   * Visual variant:
   * - "primary" (default): Blue bg (#3B82F6) + white CO — header, empty states
   * - "sub": Light blue bg (#EFF6FF) + blue CO — message bubbles
   */
  variant?: 'primary' | 'sub';
}

/**
 * Coyo avatar with "CO" vector paths.
 * Used in the Talk screen header (32px, primary) and message bubbles (28px, sub).
 */
export function CoyoAvatar({ size = 32, variant = 'primary' }: Props) {
  const bgColor = variant === 'sub' ? '#EFF6FF' : '#3B82F6';
  const fgColor = variant === 'sub' ? '#3B82F6' : '#FFFFFF';

  return (
    <Svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      accessibilityRole="image"
      accessibilityLabel="Coyo AI avatar"
    >
      {/* Circle background */}
      <Circle cx={16} cy={16} r={16} fill={bgColor} />
      {/* O ring - positioned at ~50% from left, ~34% from top */}
      <G transform="translate(16, 10.81)">
        <Path
          d="M7.329 5.125C7.329 3.90775 6.34225 2.921 5.125 2.921C3.90775 2.921 2.921 3.90775 2.921 5.125C2.921 6.34225 3.90775 7.329 5.125 7.329C6.34225 7.329 7.329 6.34225 7.329 5.125ZM10.25 5.125C10.25 7.95547 7.95547 10.25 5.125 10.25C2.29453 10.25 0 7.95547 0 5.125C0 2.29453 2.29453 0 5.125 0C7.95547 0 10.25 2.29453 10.25 5.125Z"
          fill={fgColor}
        />
      </G>
      {/* C speech bubble - positioned at ~18% from left, ~34% from top */}
      <G transform="translate(5.75, 10.81)">
        <Path
          d="M5.125 0C6.62491 0 7.97597 0.646187 8.91116 1.67091C9.45491 2.26669 9.41272 3.19044 8.81697 3.73419C8.22119 4.27794 7.29741 4.23575 6.75366 3.63997C6.34859 3.19616 5.76997 2.921 5.125 2.921C3.90775 2.921 2.921 3.90775 2.921 5.125C2.921 6.34225 3.90775 7.329 5.125 7.329C5.76997 7.329 6.34859 7.05384 6.75366 6.61003C7.29741 6.01425 8.22119 5.97206 8.81697 6.51581C9.41272 7.05956 9.45491 7.98331 8.91116 8.57909C7.97597 9.60381 6.62491 10.25 5.125 10.25C4.4185 10.25 3.74538 10.107 3.133 9.84844L2.20931 10.2938C1.69059 10.544 1.08875 10.166 1.08875 9.59016V8.28353C0.406656 7.41312 0 6.31656 0 5.125C0 2.29453 2.29453 0 5.125 0Z"
          fill={fgColor}
        />
      </G>
    </Svg>
  );
}
