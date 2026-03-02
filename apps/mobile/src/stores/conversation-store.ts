import { create } from 'zustand';
import type { Turn, TurnCorrection } from '@/types/conversation';
import type { TopicKey } from '@/navigation/types';

interface ConversationState {
  conversationId: string | null;
  topic: TopicKey | null;
  status: 'idle' | 'active' | 'ending' | 'completed';
  turns: Turn[];
  corrections: Record<string, TurnCorrection>; // turnId -> correction

  // Actions
  startConversation: (topic: TopicKey, conversationId: string) => void;
  addTurn: (turn: Turn) => void;
  updateTurnCorrectionStatus: (turnId: string, status: Turn['correctionStatus']) => void;
  updateCorrection: (turnId: string, correction: TurnCorrection) => void;
  setStatus: (status: ConversationState['status']) => void;
  reset: () => void;
}

const initialState = {
  conversationId: null,
  topic: null,
  status: 'idle' as const,
  turns: [],
  corrections: {},
};

export const useConversationStore = create<ConversationState>((set) => ({
  ...initialState,

  startConversation: (topic, conversationId) =>
    set({ topic, conversationId, status: 'active', turns: [], corrections: {} }),

  addTurn: (turn) =>
    set((state) => ({ turns: [...state.turns, turn] })),

  updateTurnCorrectionStatus: (turnId, status) =>
    set((state) => ({
      turns: state.turns.map((t) =>
        t.id === turnId ? { ...t, correctionStatus: status } : t,
      ),
    })),

  updateCorrection: (turnId, correction) =>
    set((state) => ({
      corrections: { ...state.corrections, [turnId]: correction },
    })),

  setStatus: (status) => set({ status }),

  reset: () => set(initialState),
}));
