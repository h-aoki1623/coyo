import { useState, useCallback, useRef } from 'react';
import { Audio } from 'expo-av';

import { streamGreetingEvents } from '@/api/sse-client';
import { useConversationStore } from '@/stores/conversation-store';
import { useAudioStore } from '@/stores/audio-store';
import type { Turn } from '@/types/conversation';
import type { TurnEvent } from '@/types/api';

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

interface UseGreetingReturn {
  isGreetingLoading: boolean;
  triggerGreeting: (signal?: AbortSignal) => Promise<void>;
}

/**
 * Hook for triggering an AI greeting at the start of a new conversation.
 * Streams greeting events (ai_response_chunk, tts_audio_url, etc.) and
 * adds the AI turn to the conversation store when ready.
 */
export function useGreeting(conversationId: string, topic: string): UseGreetingReturn {
  const [isGreetingLoading, setIsGreetingLoading] = useState(false);
  const bufferedAiTextRef = useRef('');
  const aiTurnAddedRef = useRef(false);
  const soundRef = useRef<Audio.Sound | null>(null);

  const addTurn = useConversationStore((s) => s.addTurn);
  const setPlaybackStatus = useAudioStore((s) => s.setPlaybackStatus);

  const addBufferedAiTurn = useCallback(() => {
    if (aiTurnAddedRef.current || !bufferedAiTextRef.current) return;
    aiTurnAddedRef.current = true;
    const aiTurn: Turn = {
      id: generateId(),
      conversationId,
      role: 'ai',
      text: bufferedAiTextRef.current,
      audioUrl: null,
      sequence: 1,
      correctionStatus: 'none',
      createdAt: new Date().toISOString(),
    };
    addTurn(aiTurn);
  }, [conversationId, addTurn]);

  const playAudio = useCallback(
    async (url: string) => {
      // Validate URL scheme before loading audio
      if (!url.startsWith('data:audio/') && !url.startsWith('https://')) return;
      try {
        if (soundRef.current) {
          await soundRef.current.unloadAsync();
          soundRef.current = null;
        }
        setPlaybackStatus('loading');
        const { sound } = await Audio.Sound.createAsync(
          { uri: url },
          { shouldPlay: true },
        );
        soundRef.current = sound;
        setPlaybackStatus('playing');

        sound.setOnPlaybackStatusUpdate((status) => {
          if (status.isLoaded && status.didJustFinish) {
            setPlaybackStatus('idle');
            sound.unloadAsync();
            soundRef.current = null;
          }
        });
      } catch {
        setPlaybackStatus('idle');
      }
    },
    [setPlaybackStatus],
  );

  const processEvent = useCallback(
    (event: TurnEvent) => {
      switch (event.type) {
        case 'ai_response_chunk':
          bufferedAiTextRef.current += event.data.text;
          break;
        case 'ai_response_done':
          bufferedAiTextRef.current = event.data.text;
          break;
        case 'tts_audio_url':
          addBufferedAiTurn();
          playAudio(event.data.url);
          break;
        case 'turn_complete':
          // Fallback: add AI turn if TTS URL was never received
          addBufferedAiTurn();
          break;
        case 'error':
          // Show whatever text was buffered
          addBufferedAiTurn();
          break;
        // Ignore stt_result, correction_result (not expected in greeting)
      }
    },
    [addBufferedAiTurn, playAudio],
  );

  const triggerGreeting = useCallback(
    async (signal?: AbortSignal) => {
      setIsGreetingLoading(true);
      bufferedAiTextRef.current = '';
      aiTurnAddedRef.current = false;

      try {
        for await (const event of streamGreetingEvents(conversationId, topic, signal)) {
          processEvent(event);
        }
      } catch (err) {
        // AbortError is expected on navigation cleanup — not a real error
        if (err instanceof Error && err.name === 'AbortError') return;
        if (__DEV__) {
          console.warn('[Greeting] Error:', err);
        }
        // Fallback: show whatever was buffered
        addBufferedAiTurn();
      } finally {
        setIsGreetingLoading(false);
      }
    },
    [conversationId, topic, processEvent, addBufferedAiTurn],
  );

  return { isGreetingLoading, triggerGreeting };
}
