import { useCallback, useEffect, useState } from 'react';
import { View, StyleSheet } from 'react-native';
import { NavigationContainer } from '@react-navigation/native';
import { StatusBar } from 'expo-status-bar';
import { useFonts } from 'expo-font';
import {
  NotoSansJP_400Regular,
  NotoSansJP_500Medium,
  NotoSansJP_700Bold,
} from '@expo-google-fonts/noto-sans-jp';
import {
  PlusJakartaSans_400Regular,
  PlusJakartaSans_500Medium,
  PlusJakartaSans_600SemiBold,
  PlusJakartaSans_700Bold,
} from '@expo-google-fonts/plus-jakarta-sans';
import * as ExpoSplashScreen from 'expo-splash-screen';

import { RootNavigator } from '@/navigation/RootNavigator';
import { useAuthStore } from '@/stores/auth-store';
import { useSuggestionsStore } from '@/stores/suggestions-store';

ExpoSplashScreen.preventAutoHideAsync();

/**
 * Maximum time we keep the native splash visible while waiting for the
 * suggestions prefetch to settle. If the API is slow or unreachable, the
 * gate falls through so the user is never stuck on the splash. Tuned to
 * cover a typical mobile network round-trip without feeling sluggish.
 */
const SPLASH_PREFETCH_TIMEOUT_MS = 2500;

export default function App() {
  const [fontsLoaded, fontError] = useFonts({
    NotoSansJP_400Regular,
    NotoSansJP_500Medium,
    NotoSansJP_700Bold,
    PlusJakartaSans_400Regular,
    PlusJakartaSans_500Medium,
    PlusJakartaSans_600SemiBold,
    PlusJakartaSans_700Bold,
  });

  const isInitialized = useAuthStore((s) => s.isInitialized);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const isEmailVerified = useAuthStore((s) => s.isEmailVerified);
  const user = useAuthStore((s) => s.user);
  const suggestionsReady = useSuggestionsStore((s) => s.isReady);
  const [prefetchTimedOut, setPrefetchTimedOut] = useState(false);

  // Initialize Firebase auth listener once. Returns the unsubscribe so the
  // listener is cleaned up if App ever unmounts (Fast Refresh in dev).
  useEffect(() => {
    const unsubscribe = useAuthStore.getState().initialize();
    return unsubscribe;
  }, []);

  // Whether the user is heading to the Home screen — only then do we need to
  // wait for the suggestions prefetch. Unauthenticated users go to the auth
  // flow, which has no prefetch dependency.
  const providerId = user?.providerData?.[0]?.providerId;
  const isHomeBound =
    isInitialized &&
    isAuthenticated &&
    (isEmailVerified || providerId !== 'password');

  // Fallback timeout: if the prefetch hasn't settled within the budget, give
  // up waiting and let Home render. Reset whenever the gate condition is no
  // longer relevant so a future sign-in waits again.
  useEffect(() => {
    if (!isHomeBound) {
      setPrefetchTimedOut(false);
      return undefined;
    }
    if (suggestionsReady) {
      return undefined;
    }
    const id = setTimeout(
      () => setPrefetchTimedOut(true),
      SPLASH_PREFETCH_TIMEOUT_MS,
    );
    return () => clearTimeout(id);
  }, [isHomeBound, suggestionsReady]);

  const fontsReady = fontsLoaded || Boolean(fontError);
  const homeReady = !isHomeBound || suggestionsReady || prefetchTimedOut;
  const appReady = fontsReady && isInitialized && homeReady;

  // Hide the OS splash screen exactly once, after the very first frame of
  // the React tree has been laid out. Using onLayout (rather than awaiting
  // `appReady` directly in an effect) prevents the brief white flash that
  // happens if `hideAsync` runs before React has anything to paint.
  const onLayoutRootView = useCallback(async () => {
    if (appReady) {
      await ExpoSplashScreen.hideAsync();
    }
  }, [appReady]);

  // While we are still gating, return null. The native splash is still up
  // (we never called hideAsync), so the user sees the brand-blue splash
  // with the white logo — exactly the Figma design.
  if (!appReady) {
    return null;
  }

  return (
    <View style={styles.root} onLayout={onLayoutRootView}>
      <NavigationContainer>
        <StatusBar style="auto" />
        <RootNavigator />
      </NavigationContainer>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
  },
});
