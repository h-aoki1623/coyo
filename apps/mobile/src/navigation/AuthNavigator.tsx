import { createNativeStackNavigator } from '@react-navigation/native-stack';

import { Colors } from '@/constants/colors';
import { WelcomeScreen } from '@/features/auth/WelcomeScreen';
import { AuthMethodScreen } from '@/features/auth/AuthMethodScreen';
import { SignUpFormScreen } from '@/features/auth/SignUpFormScreen';
import { SignInFormScreen } from '@/features/auth/SignInFormScreen';
import { EmailVerificationScreen } from '@/features/auth/EmailVerificationScreen';

import type { AuthStackParamList } from './types';

const Stack = createNativeStackNavigator<AuthStackParamList>();

export function AuthNavigator() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: Colors.surfacePrimary },
      }}
    >
      <Stack.Screen name="Welcome" component={WelcomeScreen} />
      <Stack.Screen name="AuthMethod" component={AuthMethodScreen} />
      <Stack.Screen name="SignUpForm" component={SignUpFormScreen} />
      <Stack.Screen name="SignInForm" component={SignInFormScreen} />
      <Stack.Screen
        name="EmailVerification"
        component={EmailVerificationScreen}
        options={{ gestureEnabled: false }}
      />
    </Stack.Navigator>
  );
}
