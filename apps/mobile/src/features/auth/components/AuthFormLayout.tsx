import type { ReactNode } from 'react';
import { View, Text, ScrollView, StyleSheet, KeyboardAvoidingView, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { NavBar } from '@/components/NavBar';
import { Colors } from '@/constants/colors';
import { Typography } from '@/constants/typography';

interface Props {
  title: string;
  onBack: () => void;
  children: ReactNode;
}

export function AuthFormLayout({ title, onBack, children }: Props) {
  return (
    <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
      <NavBar onBack={onBack} />

      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <ScrollView
          style={styles.flex}
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
        >
          <View style={styles.titleContainer}>
            <Text style={styles.title}>{title}</Text>
          </View>

          {children}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.surfaceCard,
  },
  flex: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingTop: 32,
    paddingBottom: 32,
  },
  titleContainer: {
    paddingBottom: 24,
  },
  title: {
    ...Typography.title.ja,
    color: Colors.textPrimary,
    textAlign: 'center',
  },
});
