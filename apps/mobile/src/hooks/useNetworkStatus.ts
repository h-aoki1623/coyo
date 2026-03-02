import { useEffect } from 'react';
import NetInfo from '@react-native-community/netinfo';
import { useAppStore } from '@/stores/app-store';

/**
 * Subscribe to network connectivity changes and sync with app store.
 * Returns current online status for convenience.
 */
export function useNetworkStatus(): boolean {
  const setOnlineStatus = useAppStore((state) => state.setOnlineStatus);
  const isOnline = useAppStore((state) => state.isOnline);

  useEffect(() => {
    const unsubscribe = NetInfo.addEventListener((state) => {
      setOnlineStatus(state.isConnected ?? false);
    });

    return () => unsubscribe();
  }, [setOnlineStatus]);

  return isOnline;
}
