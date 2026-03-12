import { create } from 'zustand';

interface AppState {
  isOnline: boolean;
  pausedConversationId: string | null;

  // Actions
  initialize: () => Promise<void>;
  setOnlineStatus: (online: boolean) => void;
  setPausedConversationId: (id: string | null) => void;
}

export const useAppStore = create<AppState>((set) => ({
  isOnline: true,
  pausedConversationId: null,

  initialize: async () => {
    // No-op: previously initialized device ID (removed)
  },

  setOnlineStatus: (isOnline) => set({ isOnline }),
  setPausedConversationId: (pausedConversationId) => set({ pausedConversationId }),
}));
