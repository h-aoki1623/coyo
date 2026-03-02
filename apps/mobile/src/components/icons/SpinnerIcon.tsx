import { useRef, useEffect } from 'react';
import { Animated, Easing } from 'react-native';
import Svg, { Circle } from 'react-native-svg';

interface Props {
  /** Diameter of the spinner in pixels. */
  size?: number;
  /** Stroke color of the spinner arc. */
  color?: string;
  /** Width of the spinner stroke. */
  strokeWidth?: number;
}

/**
 * Animated ring spinner matching the Figma Spinner component.
 * Renders a 75% arc that rotates continuously.
 */
export function SpinnerIcon({ size = 16, color = '#3B82F6', strokeWidth = 2 }: Props) {
  const rotation = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const animation = Animated.loop(
      Animated.timing(rotation, {
        toValue: 1,
        duration: 1000,
        easing: Easing.linear,
        useNativeDriver: true,
      }),
    );
    animation.start();
    return () => animation.stop();
  }, [rotation]);

  const spin = rotation.interpolate({
    inputRange: [0, 1],
    outputRange: ['0deg', '360deg'],
  });

  const r = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * r;

  return (
    <Animated.View style={{ width: size, height: size, transform: [{ rotate: spin }] }}>
      <Svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <Circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke={color}
          strokeWidth={strokeWidth}
          fill="none"
          strokeDasharray={`${circumference * 0.75} ${circumference * 0.25}`}
          strokeLinecap="round"
        />
      </Svg>
    </Animated.View>
  );
}
