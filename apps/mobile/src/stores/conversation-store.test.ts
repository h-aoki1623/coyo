import { useConversationStore } from './conversation-store';
import type { Turn, TurnCorrection } from '@/types/conversation';

// Helper to reset store between tests
function resetStore() {
  useConversationStore.getState().reset();
}

// Factory helpers for test data
function createTurn(overrides: Partial<Turn> = {}): Turn {
  return {
    id: 'turn-1',
    conversationId: 'conv-1',
    role: 'user',
    text: 'Hello',
    audioUrl: null,
    sequence: 1,
    correctionStatus: 'none',
    createdAt: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

function createCorrection(overrides: Partial<TurnCorrection> = {}): TurnCorrection {
  return {
    id: 'correction-1',
    turnId: 'turn-1',
    correctedText: 'Hello there',
    explanation: 'Added greeting word',
    items: [],
    ...overrides,
  };
}

describe('useConversationStore', () => {
  beforeEach(() => {
    resetStore();
  });

  describe('initial state', () => {
    it('has null conversationId', () => {
      expect(useConversationStore.getState().conversationId).toBeNull();
    });

    it('has null topic', () => {
      expect(useConversationStore.getState().topic).toBeNull();
    });

    it('has idle status', () => {
      expect(useConversationStore.getState().status).toBe('idle');
    });

    it('has empty turns array', () => {
      expect(useConversationStore.getState().turns).toEqual([]);
    });

    it('has empty corrections record', () => {
      expect(useConversationStore.getState().corrections).toEqual({});
    });
  });

  describe('startConversation', () => {
    it('sets topic and conversationId', () => {
      useConversationStore.getState().startConversation('sports', 'conv-123');

      const state = useConversationStore.getState();
      expect(state.topic).toBe('sports');
      expect(state.conversationId).toBe('conv-123');
    });

    it('sets status to active', () => {
      useConversationStore.getState().startConversation('business', 'conv-456');

      expect(useConversationStore.getState().status).toBe('active');
    });

    it('resets turns and corrections', () => {
      // Add some data first
      useConversationStore.getState().addTurn(createTurn());
      useConversationStore
        .getState()
        .updateCorrection('turn-1', createCorrection());

      // Start new conversation
      useConversationStore.getState().startConversation('politics', 'conv-789');

      const state = useConversationStore.getState();
      expect(state.turns).toEqual([]);
      expect(state.corrections).toEqual({});
    });

    it('works with all valid topic keys', () => {
      const topics = [
        'sports',
        'business',
        'technology',
        'politics',
        'entertainment',
      ] as const;

      for (const topic of topics) {
        useConversationStore.getState().startConversation(topic, `conv-${topic}`);
        expect(useConversationStore.getState().topic).toBe(topic);
      }
    });
  });

  describe('addTurn', () => {
    it('appends a turn to the turns array', () => {
      const turn = createTurn({ id: 'turn-1', text: 'Hello' });

      useConversationStore.getState().addTurn(turn);

      expect(useConversationStore.getState().turns).toHaveLength(1);
      expect(useConversationStore.getState().turns[0]).toEqual(turn);
    });

    it('appends multiple turns in order', () => {
      const turn1 = createTurn({ id: 'turn-1', text: 'Hello', role: 'user' });
      const turn2 = createTurn({ id: 'turn-2', text: 'Hi there', role: 'ai' });
      const turn3 = createTurn({ id: 'turn-3', text: 'How are you?', role: 'user' });

      useConversationStore.getState().addTurn(turn1);
      useConversationStore.getState().addTurn(turn2);
      useConversationStore.getState().addTurn(turn3);

      const turns = useConversationStore.getState().turns;
      expect(turns).toHaveLength(3);
      expect(turns[0].id).toBe('turn-1');
      expect(turns[1].id).toBe('turn-2');
      expect(turns[2].id).toBe('turn-3');
    });

    it('does not mutate existing turns array (immutability)', () => {
      const turn1 = createTurn({ id: 'turn-1' });
      useConversationStore.getState().addTurn(turn1);

      const turnsAfterFirst = useConversationStore.getState().turns;

      const turn2 = createTurn({ id: 'turn-2' });
      useConversationStore.getState().addTurn(turn2);

      const turnsAfterSecond = useConversationStore.getState().turns;

      // The array reference should be different (new array created)
      expect(turnsAfterFirst).not.toBe(turnsAfterSecond);
      expect(turnsAfterFirst).toHaveLength(1);
      expect(turnsAfterSecond).toHaveLength(2);
    });
  });

  describe('updateCorrection', () => {
    it('adds a correction for a turn', () => {
      const correction = createCorrection({ turnId: 'turn-1' });

      useConversationStore.getState().updateCorrection('turn-1', correction);

      expect(useConversationStore.getState().corrections['turn-1']).toEqual(
        correction,
      );
    });

    it('overwrites existing correction for same turn', () => {
      const correction1 = createCorrection({
        turnId: 'turn-1',
        explanation: 'First',
      });
      const correction2 = createCorrection({
        turnId: 'turn-1',
        explanation: 'Updated',
      });

      useConversationStore.getState().updateCorrection('turn-1', correction1);
      useConversationStore.getState().updateCorrection('turn-1', correction2);

      expect(
        useConversationStore.getState().corrections['turn-1'].explanation,
      ).toBe('Updated');
    });

    it('supports multiple corrections for different turns', () => {
      const c1 = createCorrection({ turnId: 'turn-1', id: 'c1' });
      const c2 = createCorrection({ turnId: 'turn-2', id: 'c2' });

      useConversationStore.getState().updateCorrection('turn-1', c1);
      useConversationStore.getState().updateCorrection('turn-2', c2);

      const corrections = useConversationStore.getState().corrections;
      expect(Object.keys(corrections)).toHaveLength(2);
      expect(corrections['turn-1'].id).toBe('c1');
      expect(corrections['turn-2'].id).toBe('c2');
    });

    it('does not mutate existing corrections record (immutability)', () => {
      const c1 = createCorrection({ turnId: 'turn-1' });
      useConversationStore.getState().updateCorrection('turn-1', c1);
      const correctionsAfterFirst = useConversationStore.getState().corrections;

      const c2 = createCorrection({ turnId: 'turn-2' });
      useConversationStore.getState().updateCorrection('turn-2', c2);
      const correctionsAfterSecond = useConversationStore.getState().corrections;

      expect(correctionsAfterFirst).not.toBe(correctionsAfterSecond);
    });
  });

  describe('setStatus', () => {
    it('sets status to active', () => {
      useConversationStore.getState().setStatus('active');
      expect(useConversationStore.getState().status).toBe('active');
    });

    it('sets status to ending', () => {
      useConversationStore.getState().setStatus('ending');
      expect(useConversationStore.getState().status).toBe('ending');
    });

    it('sets status to completed', () => {
      useConversationStore.getState().setStatus('completed');
      expect(useConversationStore.getState().status).toBe('completed');
    });

    it('sets status back to idle', () => {
      useConversationStore.getState().setStatus('active');
      useConversationStore.getState().setStatus('idle');
      expect(useConversationStore.getState().status).toBe('idle');
    });
  });

  describe('reset', () => {
    it('resets all state to initial values', () => {
      // Set up state
      useConversationStore.getState().startConversation('sports', 'conv-1');
      useConversationStore.getState().addTurn(createTurn());
      useConversationStore
        .getState()
        .updateCorrection('turn-1', createCorrection());

      // Reset
      useConversationStore.getState().reset();

      const state = useConversationStore.getState();
      expect(state.conversationId).toBeNull();
      expect(state.topic).toBeNull();
      expect(state.status).toBe('idle');
      expect(state.turns).toEqual([]);
      expect(state.corrections).toEqual({});
    });

    it('can start a new conversation after reset', () => {
      useConversationStore.getState().startConversation('sports', 'conv-1');
      useConversationStore.getState().reset();
      useConversationStore.getState().startConversation('business', 'conv-2');

      const state = useConversationStore.getState();
      expect(state.topic).toBe('business');
      expect(state.conversationId).toBe('conv-2');
      expect(state.status).toBe('active');
    });
  });
});
