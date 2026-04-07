import { createNativeStackNavigator } from '@react-navigation/native-stack';

import { Colors } from '@/constants/colors';
import { HomeScreen } from '@/features/home/HomeScreen';
import { TalkScreen } from '@/features/talk/TalkScreen';
import { FeedbackScreen } from '@/features/feedback/FeedbackScreen';
import { HistoryListScreen } from '@/features/history/HistoryListScreen';
import { HistoryDetailScreen } from '@/features/history/HistoryDetailScreen';
import { OfflineScreen } from '@/features/offline/OfflineScreen';
import { EmailVerificationScreen } from '@/features/auth/EmailVerificationScreen';
import { useNetworkStatus } from '@/hooks/useNetworkStatus';
import { useAuthStore } from '@/stores/auth-store';
import { AuthNavigator } from './AuthNavigator';

import type { RootStackParamList } from './types';

const Stack = createNativeStackNavigator<RootStackParamList>();

function MainNavigator() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: Colors.surfacePrimary },
      }}
    >
      <Stack.Screen name="Home" component={HomeScreen} />
      <Stack.Screen
        name="Talk"
        component={TalkScreen}
        options={{ gestureEnabled: false }}
      />
      <Stack.Screen
        name="Feedback"
        component={FeedbackScreen}
        options={{ gestureEnabled: false }}
      />
      <Stack.Screen name="HistoryList" component={HistoryListScreen} />
      <Stack.Screen name="HistoryDetail" component={HistoryDetailScreen} />
    </Stack.Navigator>
  );
}

/**
 * Root router. By the time this component renders, App.tsx has already
 * confirmed that fonts are loaded, Firebase auth has settled, and (for
 * authenticated home-bound users) the suggestions prefetch has either
 * finished or timed out — so this navigator can safely assume the auth
 * store is initialized and route directly to the appropriate stack.
 */
export function RootNavigator() {
  const isOnline = useNetworkStatus();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const isEmailVerified = useAuthStore((s) => s.isEmailVerified);
  const user = useAuthStore((s) => s.user);

  // Not authenticated -> show auth flow
  if (!isAuthenticated) {
    return (
      <>
        <AuthNavigator />
        {!isOnline ? <OfflineScreen /> : null}
      </>
    );
  }

  // Authenticated but email not verified (email/password sign-in only).
  // Google/Apple SSO users are always considered verified.
  const providerId = user?.providerData?.[0]?.providerId;
  if (!isEmailVerified && providerId === 'password') {
    return (
      <>
        <EmailVerificationScreen />
        {!isOnline ? <OfflineScreen /> : null}
      </>
    );
  }

  // Authenticated and verified -> main app
  return (
    <>
      <MainNavigator />
      {!isOnline ? <OfflineScreen /> : null}
    </>
  );
}
