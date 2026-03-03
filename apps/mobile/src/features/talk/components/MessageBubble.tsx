import { memo, useEffect, useRef } from 'react';
import { View, Text, StyleSheet, Animated } from 'react-native';
import { Colors } from '@/constants/colors';
import { Typography } from '@/constants/typography';
import { t } from '@/i18n';
import { CotoAvatar, SpinnerIcon } from '@/components/icons';
import type { Turn, TurnCorrection } from '@/types/conversation';
import { CorrectionAnnotation } from './CorrectionCard';

interface Props {
  turn: Turn;
  correction?: TurnCorrection;
  /** When true, the bubble animates in with a spring. Default: false (instant). */
  animate?: boolean;
}

/**
 * Chat message bubble for AI or User messages.
 *
 * AI messages: row layout with avatar on the left + white bubble.
 * User messages: column layout, right-padded, with blue bubble + correction annotation.
 */
export const MessageBubble = memo(function MessageBubble({ turn, correction, animate = false }: Props) {
  const springAnim = useRef(new Animated.Value(animate ? 0 : 1)).current;

  useEffect(() => {
    if (!animate) return;
    const delay = turn.role === 'ai' ? 400 : 0;
    const timer = setTimeout(() => {
      Animated.spring(springAnim, {
        toValue: 1,
        tension: 40,
        friction: 5,
        useNativeDriver: true,
      }).start();
    }, delay);
    return () => clearTimeout(timer);
  }, [animate, springAnim, turn.role]);

  const bubbleAnimStyle = {
    opacity: springAnim,
    transform: [
      {
        scale: springAnim.interpolate({
          inputRange: [0, 1],
          outputRange: [0, 1],
        }),
      },
    ],
  };

  const isUser = turn.role === 'user';

  if (isUser) {
    return (
      <Animated.View
        style={[styles.userContainer, bubbleAnimStyle]}
        accessibilityRole="text"
        accessibilityLabel={`You said: ${turn.text}`}
      >
        <View style={styles.userBubble}>
          <Text style={[styles.text, styles.userText]}>{turn.text}</Text>
        </View>
        <CorrectionAnnotation
          correctionStatus={turn.correctionStatus}
          correction={correction}
        />
      </Animated.View>
    );
  }

  return (
    <View
      style={styles.aiContainer}
      accessibilityRole="text"
      accessibilityLabel={`Coto said: ${turn.text}`}
    >
      <CotoAvatar size={28} variant="sub" />
      <Animated.View style={[styles.aiBubble, bubbleAnimStyle]}>
        <Text style={[styles.text, styles.aiText]}>{turn.text}</Text>
      </Animated.View>
    </View>
  );
});

interface TypingBubbleProps {
  text: string;
}

/**
 * Typing bubble shown while AI is streaming a text response.
 * Displays the partial text inside an AI-style bubble with avatar.
 */
export const TypingBubble = memo(function TypingBubble({ text }: TypingBubbleProps) {
  return (
    <View style={styles.aiContainer}>
      <CotoAvatar size={28} variant="sub" />
      <View style={styles.aiBubble}>
        <Text style={[styles.text, styles.aiText]}>{text}</Text>
      </View>
    </View>
  );
});

/**
 * AI typing indicator — 3 dots inside a white AI bubble.
 * Shown while waiting for the AI to start responding after user speech is processed.
 */
export const AiTypingBubble = memo(function AiTypingBubble() {
  const springAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const timer = setTimeout(() => {
      Animated.spring(springAnim, {
        toValue: 1,
        tension: 40,
        friction: 5,
        useNativeDriver: true,
      }).start();
    }, 400);
    return () => clearTimeout(timer);
  }, [springAnim]);

  const animStyle = {
    opacity: springAnim,
    transform: [
      {
        scale: springAnim.interpolate({
          inputRange: [0, 1],
          outputRange: [0, 1],
        }),
      },
    ],
  };

  return (
    <View
      style={styles.aiContainer}
      accessibilityRole="text"
      accessibilityLabel="Coto is typing"
    >
      <CotoAvatar size={28} variant="sub" />
      <Animated.View style={[styles.aiBubble, styles.typingIndicatorBubble, animStyle]}>
        <View style={styles.typingDots}>
          <View style={[styles.typingDot, styles.typingDotMuted]} />
          <View style={styles.typingDot} />
          <View style={[styles.typingDot, styles.typingDotMuted]} />
        </View>
      </Animated.View>
    </View>
  );
});

/**
 * User processing indicator — blue bubble with spinner + "Processing..." text.
 * Shown while the user's audio is being transcribed (before stt_result arrives).
 * Uses a separate container (no pl-52) — the bubble is content-width, right-aligned.
 */
export const ProcessingBubble = memo(function ProcessingBubble() {
  const springAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.spring(springAnim, {
      toValue: 1,
      tension: 40,
      friction: 5,
      useNativeDriver: true,
    }).start();
  }, [springAnim]);

  const animStyle = {
    opacity: springAnim,
    transform: [
      {
        scale: springAnim.interpolate({
          inputRange: [0, 1],
          outputRange: [0, 1],
        }),
      },
    ],
  };

  return (
    <Animated.View
      style={[styles.processingContainer, animStyle]}
      accessibilityRole="text"
      accessibilityLabel={t('talk.processing')}
    >
      <View style={styles.processingBubble}>
        <SpinnerIcon size={16} color="#FFFFFF" strokeWidth={2} />
        <Text style={styles.processingText}>{t('talk.processing')}</Text>
      </View>
    </Animated.View>
  );
});

const styles = StyleSheet.create({
  // -- AI container (row layout with avatar) --
  aiContainer: {
    flexDirection: 'row',
    gap: 8,
    paddingLeft: 20,
    paddingRight: 36,
    alignItems: 'flex-start',
  },
  // -- User container (column layout, padded left) --
  userContainer: {
    paddingLeft: 72,
    paddingRight: 20,
    gap: 8,
  },
  // -- Processing container (right-aligned, no left padding) --
  processingContainer: {
    paddingRight: 20,
    alignItems: 'flex-end',
  },
  // -- User bubble --
  userBubble: {
    backgroundColor: Colors.buttonPrimaryBg,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 6,
    borderBottomLeftRadius: 20,
    borderBottomRightRadius: 20,
    padding: 12,
  },
  // -- AI bubble --
  aiBubble: {
    flex: 1,
    backgroundColor: Colors.chatAiBubbleBg,
    borderWidth: 1,
    borderColor: Colors.chatAiBubbleBorder,
    borderTopLeftRadius: 6,
    borderTopRightRadius: 20,
    borderBottomLeftRadius: 20,
    borderBottomRightRadius: 20,
    padding: 13,
  },
  // -- Text --
  text: {
    ...Typography.body.en,
  },
  userText: {
    color: Colors.textInverse,
  },
  aiText: {
    color: Colors.textPrimary,
  },
  // -- User processing bubble --
  processingBubble: {
    backgroundColor: Colors.buttonPrimaryBg,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 6,
    borderBottomLeftRadius: 20,
    borderBottomRightRadius: 20,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    padding: 12,
  },
  processingText: {
    ...Typography.body.en,
    color: Colors.textInverse,
  },
  // -- AI typing indicator --
  typingIndicatorBubble: {
    flex: 0,
    width: 80,
    height: 50,
    padding: 0,
    paddingHorizontal: 13,
    paddingVertical: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  typingDots: {
    flexDirection: 'row',
    gap: 5,
    alignItems: 'center',
  },
  typingDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: Colors.chevron,
  },
  typingDotMuted: {
    opacity: 0.6,
  },
});
