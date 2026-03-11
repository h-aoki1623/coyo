import Svg, { Path } from 'react-native-svg';

interface Props {
  size?: number;
  color?: string;
}

/**
 * Apple logo icon for the Apple sign-in button.
 */
export function AppleIcon({ size = 20, color = '#FFFFFF' }: Props) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M17.05 20.28C16.07 21.23 15 21.08 13.97 20.63C12.88 20.17 11.88 20.15 10.73 20.63C9.28 21.25 8.52 21.07 7.63 20.28C2.48 14.94 3.22 6.84 9.09 6.55C10.44 6.62 11.39 7.29 12.19 7.35C13.37 7.11 14.5 6.42 15.77 6.51C17.29 6.63 18.44 7.24 19.2 8.35C15.98 10.22 16.72 14.51 19.67 15.76C19.06 17.36 18.27 18.94 17.04 20.29L17.05 20.28ZM12.05 6.49C11.9 4.35 13.64 2.57 15.64 2.4C15.93 4.86 13.43 6.72 12.05 6.49Z"
        fill={color}
      />
    </Svg>
  );
}
