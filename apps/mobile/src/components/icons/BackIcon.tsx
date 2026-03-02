import Svg, { Path } from 'react-native-svg';

interface Props {
  size?: number;
  color?: string;
}

export function BackIcon({ size = 16, color = '#3B82F6' }: Props) {
  const width = size * 0.5625;
  return (
    <Svg width={width} height={size} viewBox="0 0 9 16" fill="none">
      <Path
        d="M7.29289 0.292893C7.68342 -0.0976311 8.31643 -0.0976311 8.70696 0.292893C9.09748 0.683417 9.09748 1.31643 8.70696 1.70696L2.41399 7.99992L8.70696 14.2929C9.09748 14.6834 9.09748 15.3164 8.70696 15.707C8.31643 16.0975 7.68342 16.0975 7.29289 15.707L0.292893 8.70696C-0.0976311 8.31643 -0.0976311 7.68342 0.292893 7.29289L7.29289 0.292893Z"
        fill={color}
      />
    </Svg>
  );
}
