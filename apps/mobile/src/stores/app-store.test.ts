import { useAppStore } from './app-store';

// Helper to reset store between tests
function resetStore() {
  useAppStore.setState({
    isOnline: true,
    pausedConversationId: null,
  });
}

describe('useAppStore', () => {
  beforeEach(() => {
    resetStore();
    jest.clearAllMocks();
  });

  describe('initial state', () => {
    it('has isOnline set to true', () => {
      expect(useAppStore.getState().isOnline).toBe(true);
    });

    it('has null pausedConversationId', () => {
      expect(useAppStore.getState().pausedConversationId).toBeNull();
    });
  });

  describe('initialize', () => {
    it('completes without error', async () => {
      await expect(useAppStore.getState().initialize()).resolves.toBeUndefined();
    });
  });

  describe('setOnlineStatus', () => {
    it('sets online status to false', () => {
      useAppStore.getState().setOnlineStatus(false);
      expect(useAppStore.getState().isOnline).toBe(false);
    });

    it('sets online status to true', () => {
      useAppStore.getState().setOnlineStatus(false);
      useAppStore.getState().setOnlineStatus(true);
      expect(useAppStore.getState().isOnline).toBe(true);
    });

    it('does not affect other state', () => {
      useAppStore.getState().setOnlineStatus(false);

      expect(useAppStore.getState().pausedConversationId).toBeNull();
    });
  });

  describe('setPausedConversationId', () => {
    it('sets a paused conversation ID', () => {
      useAppStore.getState().setPausedConversationId('conv-paused-1');
      expect(useAppStore.getState().pausedConversationId).toBe('conv-paused-1');
    });

    it('clears the paused conversation ID with null', () => {
      useAppStore.getState().setPausedConversationId('conv-paused-1');
      useAppStore.getState().setPausedConversationId(null);
      expect(useAppStore.getState().pausedConversationId).toBeNull();
    });

    it('does not affect other state', () => {
      useAppStore.getState().setOnlineStatus(false);
      useAppStore.getState().setPausedConversationId('conv-1');

      expect(useAppStore.getState().isOnline).toBe(false);
    });
  });
});
