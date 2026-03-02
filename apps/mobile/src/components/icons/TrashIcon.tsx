import Svg, { Path, Line } from 'react-native-svg';

interface Props {
  size?: number;
  color?: string;
}

/**
 * Trash can icon for delete actions.
 * Used in the history list swipe-to-delete action.
 */
export function TrashIcon({ size = 20, color = '#FFFFFF' }: Props) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      {/* Lid */}
      <Path
        d="M3 6h18"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Can body */}
      <Path
        d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Handle */}
      <Path
        d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Vertical lines inside */}
      <Line
        x1={10}
        y1={11}
        x2={10}
        y2={17}
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
      />
      <Line
        x1={14}
        y1={11}
        x2={14}
        y2={17}
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
      />
    </Svg>
  );
}
