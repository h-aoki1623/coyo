import { create } from 'zustand';
import { getOrCreateDeviceId } from '@/services/device-id';

interface AppState {
  isOnline: boolean;
  deviceId: string | null;
  pausedConversationId: string | null;

  // Actions
  initialize: () => Promise<void>;
  setOnlineStatus: (online: boolean) => void;
  setPausedConversationId: (id: string | null) => void;
}

export const useAppStore = create<AppState>((set) => ({
  isOnline: true,
  deviceId: null,
  pausedConversationId: null,

  initialize: async () => {
    const deviceId = await getOrCreateDeviceId();
    set({ deviceId });
  },

  setOnlineStatus: (isOnline) => set({ isOnline }),
  setPausedConversationId: (pausedConversationId) => set({ pausedConversationId }),
}));
