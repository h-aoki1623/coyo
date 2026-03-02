import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { Colors } from '@/constants/colors';
import { HomeScreen } from '@/features/home/HomeScreen';
import { TalkScreen } from '@/features/talk/TalkScreen';
import { FeedbackScreen } from '@/features/feedback/FeedbackScreen';
import { HistoryListScreen } from '@/features/history/HistoryListScreen';
import { HistoryDetailScreen } from '@/features/history/HistoryDetailScreen';
import { OfflineScreen } from '@/features/offline/OfflineScreen';
import { useNetworkStatus } from '@/hooks/useNetworkStatus';
import type { RootStackParamList } from './types';

const Stack = createNativeStackNavigator<RootStackParamList>();

export function RootNavigator() {
  const isOnline = useNetworkStatus();

  return (
    <>
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

      {/* Offline overlay - shown on top of everything when network is disconnected */}
      {!isOnline ? <OfflineScreen /> : null}
    </>
  );
}
