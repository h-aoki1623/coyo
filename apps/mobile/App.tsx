import { useCallback, useEffect } from 'react';
import { View, StyleSheet, Linking } from 'react-native';
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
import { linking } from '@/navigation/linking';
import { signOut as firebaseSignOut } from '@/services/firebase-auth';
import { useAuthStore } from '@/stores/auth-store';
import { useSuggestionsStore } from '@/stores/suggestions-store';

ExpoSplashScreen.preventAutoHideAsync();

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

  // Initialize Firebase auth listener once. Returns the unsubscribe so the
  // listener is cleaned up if App ever unmounts (Fast Refresh in dev).
  useEffect(() => {
    const unsubscribe = useAuthStore.getState().initialize();
    return unsubscribe;
  }, []);

  // When a coyo://password-reset-done URL arrives (after the user resets
  // their password on Firebase's hosted page), sign out so the AuthNavigator
  // mounts and the deep link resolves to the PasswordResetSuccess screen.
  // Firebase revokes refresh tokens on password change, but the in-memory
  // session may still appear authenticated momentarily — signing out eagerly
  // avoids a race where the deep link arrives before onAuthStateChanged fires.
  useEffect(() => {
    const isResetDoneUrl = (url: string | null): boolean =>
      url === 'coyo://password-reset-done'
      || (url?.startsWith('coyo://password-reset-done?') ?? false);

    const handleResetDoneUrl = (url: string | null) => {
      if (!isResetDoneUrl(url)) return;
      firebaseSignOut().catch(() => {});
    };

    const subscription = Linking.addEventListener('url', ({ url }) => {
      handleResetDoneUrl(url);
    });

    Linking.getInitialURL().then(handleResetDoneUrl).catch(() => {});

    return () => subscription.remove();
  }, []);

  // Whether the user is heading to the Home screen — only then do we need
  // to wait for the suggestions prefetch. Unauthenticated users go to the
  // auth flow, which has no prefetch dependency.
  const providerId = user?.providerData?.[0]?.providerId;
  const isHomeBound =
    isInitialized &&
    isAuthenticated &&
    (isEmailVerified || providerId !== 'password');

  // The splash gate waits for the suggestions prefetch to settle. We used
  // to have a 2.5s fallback timeout here, but it was too aggressive on
  // cold starts with a warm-up LLM / cold Cloud Run instance — the splash
  // would release while the prefetch was still in flight and the user
  // would see an empty Home with suggestions popping in seconds later.
  //
  // We rely on `isReady` alone now. It is set in the `finally` block of
  // `suggestionsStore.prefetch()` on BOTH success and failure paths, and
  // `apiClient` has a per-request AbortController timeout (15s by default)
  // so a genuinely hung request will still eventually mark `isReady` —
  // the splash will never stall indefinitely.
  const fontsReady = fontsLoaded || Boolean(fontError);
  const homeReady = !isHomeBound || suggestionsReady;
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
      <NavigationContainer linking={linking}>
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
