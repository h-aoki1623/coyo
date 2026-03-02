import Svg, { Path, Line } from 'react-native-svg';

interface Props {
  size?: number;
  color?: string;
}

/**
 * WiFi-off icon with diagonal slash.
 * Displayed on the OfflineScreen when network is unavailable.
 */
export function OfflineIcon({ size = 56, color = '#94A3B8' }: Props) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      {/* Diagonal slash */}
      <Path
        d="M1 1l22 22"
        stroke={color}
        strokeWidth={2.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* WiFi arcs - partial, showing "off" state */}
      <Path
        d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55"
        stroke={color}
        strokeWidth={2.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Path
        d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39"
        stroke={color}
        strokeWidth={2.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Path
        d="M10.71 5.05A16 16 0 0 1 22.56 9"
        stroke={color}
        strokeWidth={2.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Path
        d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88"
        stroke={color}
        strokeWidth={2.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Path
        d="M8.53 16.11a6 6 0 0 1 6.95 0"
        stroke={color}
        strokeWidth={2.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Center dot */}
      <Line
        x1={12}
        y1={20}
        x2={12.01}
        y2={20}
        stroke={color}
        strokeWidth={2.5}
        strokeLinecap="round"
      />
    </Svg>
  );
}
