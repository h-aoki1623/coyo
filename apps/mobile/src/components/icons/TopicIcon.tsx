import Svg, { Path, Rect } from 'react-native-svg';
import type { Topic } from '@/constants/topics';

interface Props {
  icon: Topic['icon'];
  size?: number;
  color?: string;
}

/**
 * Maps a topic icon name to the corresponding SVG icon component.
 * Used in topic cards on the Home screen.
 */
export function TopicIcon({ icon, size = 20, color = '#2563EB' }: Props) {
  switch (icon) {
    case 'globe':
      return <GlobeIcon size={size} color={color} />;
    case 'briefcase':
      return <BriefcaseIcon size={size} color={color} />;
    case 'building':
      return <BuildingIcon size={size} color={color} />;
    case 'monitor':
      return <MonitorIcon size={size} color={color} />;
    case 'film':
      return <FilmIcon size={size} color={color} />;
  }
}

function GlobeIcon({ size, color }: { size: number; color: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Z"
        stroke={color}
        strokeWidth={1.8}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Path
        d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10A15.3 15.3 0 0 1 12 2Z"
        stroke={color}
        strokeWidth={1.8}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

function BriefcaseIcon({ size, color }: { size: number; color: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Rect
        x={2}
        y={7}
        width={20}
        height={14}
        rx={2}
        stroke={color}
        strokeWidth={1.8}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Path
        d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"
        stroke={color}
        strokeWidth={1.8}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Path
        d="M12 12v.01"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
      />
    </Svg>
  );
}

function BuildingIcon({ size, color }: { size: number; color: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M3 21h18M5 21V7l8-4v18M19 21V11l-6-4"
        stroke={color}
        strokeWidth={1.8}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Path
        d="M9 9v.01M9 12v.01M9 15v.01M9 18v.01"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
      />
    </Svg>
  );
}

function MonitorIcon({ size, color }: { size: number; color: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Rect
        x={2}
        y={3}
        width={20}
        height={14}
        rx={2}
        stroke={color}
        strokeWidth={1.8}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Path
        d="M8 21h8M12 17v4"
        stroke={color}
        strokeWidth={1.8}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

function FilmIcon({ size, color }: { size: number; color: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Rect
        x={2}
        y={2}
        width={20}
        height={20}
        rx={2.18}
        stroke={color}
        strokeWidth={1.8}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <Path
        d="M7 2v20M17 2v20M2 12h20M2 7h5M2 17h5M17 17h5M17 7h5"
        stroke={color}
        strokeWidth={1.8}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}
