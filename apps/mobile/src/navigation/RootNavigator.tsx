import { useEffect } from 'react';
import { View, ActivityIndicator, StyleSheet } from 'react-native';

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

export function RootNavigator() {
  const isOnline = useNetworkStatus();
  const isInitialized = useAuthStore((s) => s.isInitialized);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const isEmailVerified = useAuthStore((s) => s.isEmailVerified);
  const user = useAuthStore((s) => s.user);

  useEffect(() => {
    const unsubscribe = useAuthStore.getState().initialize();
    return unsubscribe;
  }, []);

  // Show loading while auth state is being determined
  if (!isInitialized) {
    return (
      <View style={styles.loading}>
        <ActivityIndicator size="large" color={Colors.buttonPrimaryBg} />
      </View>
    );
  }

  // Not authenticated -> show auth flow
  if (!isAuthenticated) {
    return (
      <>
        <AuthNavigator />
        {!isOnline ? <OfflineScreen /> : null}
      </>
    );
  }

  // Authenticated but email not verified (email/password sign-in only)
  // Google/Apple SSO users are always considered verified
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

const styles = StyleSheet.create({
  loading: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: Colors.surfacePrimary,
  },
});
