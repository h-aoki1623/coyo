# React Native Coding Style

> This file extends [common/coding-style.md](../common/coding-style.md) and [typescript/coding-style.md](../typescript/coding-style.md) with React Native specific content.

## Component Structure

Use functional components with typed props:

```typescript
import { StyleSheet, Pressable, Text } from 'react-native'

interface Props {
  title: string
  onPress: () => void
}

export function FeatureCard({ title, onPress }: Props) {
  return (
    <Pressable style={styles.container} onPress={onPress}>
      <Text style={styles.title}>{title}</Text>
    </Pressable>
  )
}

const styles = StyleSheet.create({
  container: {
    padding: 16,
  },
  title: {
    fontSize: 18,
    fontWeight: '600',
  },
})
```

## Styling

- ALWAYS use `StyleSheet.create()` for static styles (enables native optimization)
- Use inline styles only for truly dynamic values (e.g., `{ opacity: animatedValue }`)
- Co-locate styles at the bottom of the component file

```typescript
// WRONG: Object literals on every render
<View style={{ padding: 16, margin: 8 }} />

// CORRECT: StyleSheet.create
<View style={styles.container} />

// OK: Dynamic styles combined with static
<View style={[styles.container, { opacity }]} />
```

## Platform-Specific Code

Use platform-specific file extensions for significant differences:

```
Button.tsx          # Shared logic
Button.ios.tsx      # iOS-specific implementation
Button.android.tsx  # Android-specific implementation
```

Use `Platform.select` or `Platform.OS` for minor differences:

```typescript
import { Platform } from 'react-native'

const shadow = Platform.select({
  ios: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  android: {
    elevation: 4,
  },
})
```

## Imports

Order imports as follows:

```typescript
// 1. React / React Native
import { useState, useCallback } from 'react'
import { View, Text, StyleSheet } from 'react-native'

// 2. Third-party libraries
import { useNavigation } from '@react-navigation/native'
import Animated from 'react-native-reanimated'

// 3. Local modules (absolute paths)
import { useAuth } from '@/hooks/useAuth'
import { UserCard } from '@/components/UserCard'

// 4. Types
import type { User } from '@/types'
```

## Forbidden Web APIs

These Web APIs are NOT available in React Native:

- `window`, `document`, `localStorage`, `sessionStorage`
- `XMLHttpRequest` (use `fetch` or Axios)
- CSS class names, CSS-in-JS libraries targeting DOM (styled-components for web)
- `innerHTML`, `querySelector`, DOM manipulation

## Reference

See skill: `react-native-patterns` for component composition, navigation, state management, forms, gestures, animations, and accessibility patterns.
See skill: `react-native-best-practices` for performance optimization and FPS/TTI/bundle size guidelines.
