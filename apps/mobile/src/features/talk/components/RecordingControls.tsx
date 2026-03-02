import { useEffect, useRef } from 'react';
import { View, Text, Pressable, Animated, StyleSheet, Platform } from 'react-native';
import { Colors } from '@/constants/colors';
import { Typography } from '@/constants/typography';
import { t } from '@/i18n';
import { CloseIcon, SendIcon } from '@/components/icons';

interface Props {
  onCancel: () => void;
  onSend: () => void;
}

const BAR_COUNT = 20;

/**
 * Recording controls shown while the user is actively recording audio.
 * Displays "Speak now..." text, animated waveform bars, and cancel/send buttons.
 */
export function RecordingControls({ onCancel, onSend }: Props) {
  return (
    <View style={styles.container}>
      <Text style={styles.speakNowText}>{t('talk.speakNow')}</Text>
      <WaveformVisualizer />
      <View style={styles.controlsRow}>
        <Pressable
          style={({ pressed }) => [
            styles.cancelButton,
            pressed && styles.buttonPressed,
          ]}
          onPress={onCancel}
          testID="cancel-recording"
          accessibilityRole="button"
          accessibilityLabel={t('common.cancel')}
        >
          <CloseIcon size={18} color="#64748B" />
        </Pressable>
        <Pressable
          style={({ pressed }) => [
            styles.sendButton,
            pressed && styles.buttonPressed,
          ]}
          onPress={onSend}
          testID="send-recording"
          accessibilityRole="button"
          accessibilityLabel="Send recording"
        >
          <SendIcon size={26} color="#FFFFFF" />
        </Pressable>
        <View style={styles.spacer} />
      </View>
    </View>
  );
}

/**
 * Animated waveform bars that simulate audio visualization.
 * Each bar oscillates at a slightly different speed/phase for a natural look.
 */
function WaveformVisualizer() {
  const animatedValues = useRef(
    Array.from({ length: BAR_COUNT }, () => new Animated.Value(0)),
  ).current;

  useEffect(() => {
    const timeouts: ReturnType<typeof setTimeout>[] = [];
    const animations = animatedValues.map((value, index) =>
      Animated.loop(
        Animated.sequence([
          Animated.timing(value, {
            toValue: 1,
            duration: 300 + (index % 5) * 80,
            useNativeDriver: false,
          }),
          Animated.timing(value, {
            toValue: 0,
            duration: 300 + (index % 5) * 80,
            useNativeDriver: false,
          }),
        ]),
      ),
    );

    // Stagger the start of each bar animation
    animations.forEach((anim, index) => {
      const timeout = setTimeout(() => anim.start(), index * 40);
      timeouts.push(timeout);
    });

    return () => {
      timeouts.forEach(clearTimeout);
      animations.forEach((anim) => anim.stop());
    };
  }, [animatedValues]);

  return (
    <View style={styles.waveformContainer}>
      {animatedValues.map((value, index) => {
        const height = value.interpolate({
          inputRange: [0, 1],
          outputRange: [6, 24 + (index % 3) * 8],
        });

        return (
          <Animated.View
            key={index}
            style={[
              styles.waveformBar,
              { height },
            ]}
          />
        );
      })}
    </View>
  );
}

const CANCEL_SIZE = 44;
const SEND_SIZE = 62;

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    paddingTop: 16,
    paddingBottom: 40,
    gap: 16,
  },
  speakNowText: {
    ...Typography.bodySmall.en,
    color: Colors.buttonGhostText,
  },
  // Waveform
  waveformContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    height: 32,
    gap: 3,
    paddingHorizontal: 32,
  },
  waveformBar: {
    width: 3,
    borderRadius: 2,
    backgroundColor: Colors.accentMuted,
  },
  // Control buttons
  controlsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
  },
  cancelButton: {
    width: CANCEL_SIZE,
    height: CANCEL_SIZE,
    borderRadius: CANCEL_SIZE / 2,
    backgroundColor: Colors.borderSubtle,
    justifyContent: 'center',
    alignItems: 'center',
  },
  sendButton: {
    width: SEND_SIZE,
    height: SEND_SIZE,
    borderRadius: SEND_SIZE / 2,
    backgroundColor: Colors.buttonPrimaryBg,
    justifyContent: 'center',
    alignItems: 'center',
    ...Platform.select({
      ios: {
        shadowColor: 'rgba(59,130,246,1)',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.35,
        shadowRadius: 20,
      },
      android: {
        elevation: 8,
      },
    }),
  },
  spacer: {
    width: CANCEL_SIZE,
  },
  buttonPressed: {
    opacity: 0.7,
    transform: [{ scale: 0.95 }],
  },
});
