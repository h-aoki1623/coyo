import { useState, useCallback, useRef } from 'react';
import { Alert } from 'react-native';
import { Audio } from 'expo-av';
import { streamTurnEvents } from '@/api/sse-client';
import { useConversationStore } from '@/stores/conversation-store';
import { useAudioStore } from '@/stores/audio-store';
import type { Turn, TurnCorrection, CorrectionItem } from '@/types/conversation';
import type { TurnEvent, TurnCorrectionEventData } from '@/types/api';
import { buildAudioFormData } from './useAudioRecording';

interface UseTurnStreamingReturn {
  isStreaming: boolean;
  isUserProcessing: boolean;
  isAiThinking: boolean;
  processTurn: (audioUri: string) => Promise<void>;
}

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

function mapCorrectionData(
  turnId: string,
  data: TurnCorrectionEventData,
): TurnCorrection {
  const items: CorrectionItem[] = data.items.map((item) => ({
    id: generateId(),
    original: item.original,
    corrected: item.corrected,
    originalSentence: item.originalSentence,
    correctedSentence: item.correctedSentence,
    type: item.type,
    explanation: item.explanation,
  }));

  return {
    id: generateId(),
    turnId,
    correctedText: data.correctedText,
    explanation: data.explanation,
    items,
  };
}

/**
 * Hook for processing a conversation turn via SSE streaming.
 * Sends audio, processes streamed events, and updates stores.
 */
export function useTurnStreaming(conversationId: string): UseTurnStreamingReturn {
  const [isStreaming, setIsStreaming] = useState(false);
  const [isUserProcessing, setIsUserProcessing] = useState(false);
  const [isAiThinking, setIsAiThinking] = useState(false);
  const soundRef = useRef<Audio.Sound | null>(null);
  const bufferedAiTextRef = useRef('');
  const aiTurnAddedRef = useRef(false);

  const addTurn = useConversationStore((s) => s.addTurn);
  const updateTurnCorrectionStatus = useConversationStore((s) => s.updateTurnCorrectionStatus);
  const updateCorrection = useConversationStore((s) => s.updateCorrection);
  const setRecordingStatus = useAudioStore((s) => s.setRecordingStatus);
  const setPlaybackStatus = useAudioStore((s) => s.setPlaybackStatus);

  const playAudio = useCallback(
    async (url: string) => {
      try {
        // Unload previous sound if any
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

  const addBufferedAiTurn = useCallback(() => {
    if (aiTurnAddedRef.current || !bufferedAiTextRef.current) return;
    aiTurnAddedRef.current = true;
    const aiTurn: Turn = {
      id: generateId(),
      conversationId,
      role: 'ai',
      text: bufferedAiTextRef.current,
      audioUrl: null,
      sequence: Date.now(),
      correctionStatus: 'none',
      createdAt: new Date().toISOString(),
    };
    addTurn(aiTurn);
    setIsAiThinking(false);
  }, [conversationId, addTurn]);

  const processEvent = useCallback(
    (event: TurnEvent, ctx: { turnId: string | null; correctionReceived: boolean }) => {
      switch (event.type) {
        case 'stt_result': {
          const userTurn: Turn = {
            id: generateId(),
            conversationId,
            role: 'user',
            text: event.data.text,
            audioUrl: null,
            sequence: Date.now(),
            correctionStatus: 'pending',
            createdAt: new Date().toISOString(),
          };
          ctx.turnId = userTurn.id;
          addTurn(userTurn);
          setIsUserProcessing(false);
          setIsAiThinking(true);
          break;
        }
        case 'ai_response_chunk': {
          // Buffer text internally — UI keeps showing dots until audio plays
          bufferedAiTextRef.current += event.data.text;
          break;
        }
        case 'ai_response_done': {
          // Store the complete text but don't add AI turn yet — wait for tts_audio_url
          bufferedAiTextRef.current = event.data.text;
          break;
        }
        case 'tts_audio_url': {
          // Audio ready: reveal AI response text and start playback
          addBufferedAiTurn();
          playAudio(event.data.url);
          break;
        }
        case 'correction_result': {
          if (ctx.turnId) {
            ctx.correctionReceived = true;
            const correction = mapCorrectionData(ctx.turnId, event.data);
            updateCorrection(ctx.turnId, correction);
            const newStatus = event.data.items.length > 0 ? 'has_corrections' : 'clean';
            updateTurnCorrectionStatus(ctx.turnId, newStatus as 'has_corrections' | 'clean');
          }
          break;
        }
        case 'turn_complete': {
          // Fallback: add AI turn if tts_audio_url was never received
          addBufferedAiTurn();
          // Backend omits correction event when no corrections found.
          // Transition pending → clean if no correction_result was received.
          if (ctx.turnId && !ctx.correctionReceived) {
            updateTurnCorrectionStatus(ctx.turnId, 'clean');
          }
          setRecordingStatus('idle');
          break;
        }
        case 'error': {
          // Fallback: show whatever AI text was buffered before the error
          addBufferedAiTurn();
          Alert.alert('Error', event.data.message);
          setRecordingStatus('idle');
          break;
        }
      }
    },
    [conversationId, addTurn, updateTurnCorrectionStatus, updateCorrection, setRecordingStatus, playAudio, addBufferedAiTurn],
  );

  const processTurn = useCallback(
    async (audioUri: string) => {
      setIsStreaming(true);
      setIsUserProcessing(true);
      setIsAiThinking(false);
      bufferedAiTextRef.current = '';
      aiTurnAddedRef.current = false;

      const ctx = { turnId: null as string | null, correctionReceived: false };
      const formData = buildAudioFormData(audioUri);

      try {
        for await (const event of streamTurnEvents(conversationId, formData)) {
          processEvent(event, ctx);
        }
      } catch (err) {
        if (__DEV__) {
          console.warn('[TurnStreaming] Error:', err);
        }
        // Fallback: show whatever AI text was buffered before the error
        addBufferedAiTurn();
        Alert.alert(
          'Streaming Error',
          'Lost connection during the conversation. Please try speaking again.',
        );
        setRecordingStatus('idle');
        setIsUserProcessing(false);
      } finally {
        setIsStreaming(false);
        setIsAiThinking(false);
      }
    },
    [conversationId, processEvent, setRecordingStatus, addBufferedAiTurn],
  );

  return { isStreaming, isUserProcessing, isAiThinking, processTurn };
}
