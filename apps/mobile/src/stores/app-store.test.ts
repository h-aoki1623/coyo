import { useAppStore } from './app-store';

// Mock device-id service at module level
jest.mock('@/services/device-id', () => ({
  getOrCreateDeviceId: jest.fn(() => Promise.resolve('mock-device-id-xyz')),
}));

// Import after mock setup
import { getOrCreateDeviceId } from '@/services/device-id';

const mockGetOrCreateDeviceId = getOrCreateDeviceId as jest.MockedFunction<
  typeof getOrCreateDeviceId
>;

// Helper to reset store between tests
function resetStore() {
  useAppStore.setState({
    isOnline: true,
    deviceId: null,
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

    it('has null deviceId', () => {
      expect(useAppStore.getState().deviceId).toBeNull();
    });

    it('has null pausedConversationId', () => {
      expect(useAppStore.getState().pausedConversationId).toBeNull();
    });
  });

  describe('initialize', () => {
    it('retrieves device ID and sets it in state', async () => {
      mockGetOrCreateDeviceId.mockResolvedValue('device-id-abc');

      await useAppStore.getState().initialize();

      expect(useAppStore.getState().deviceId).toBe('device-id-abc');
      expect(mockGetOrCreateDeviceId).toHaveBeenCalledTimes(1);
    });

    it('sets the device ID returned by getOrCreateDeviceId', async () => {
      mockGetOrCreateDeviceId.mockResolvedValue('another-device-id');

      await useAppStore.getState().initialize();

      expect(useAppStore.getState().deviceId).toBe('another-device-id');
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
      useAppStore.setState({ deviceId: 'test-device' });
      useAppStore.getState().setOnlineStatus(false);

      expect(useAppStore.getState().deviceId).toBe('test-device');
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
