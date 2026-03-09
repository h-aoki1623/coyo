# React Native Patterns

> This file extends [common/patterns.md](../common/patterns.md) and [typescript/patterns.md](../typescript/patterns.md) with React Native specific content.

## Navigation

Use **Expo Router** (file-based routing) or **React Navigation** (stack-based):

```typescript
// Expo Router: file-based (app/ directory)
// app/(tabs)/home.tsx  → /home
// app/user/[id].tsx    → /user/:id

// React Navigation: stack-based
import { createNativeStackNavigator } from '@react-navigation/native-stack'

type RootStackParamList = {
  Home: undefined
  UserDetail: { userId: string }
}

const Stack = createNativeStackNavigator<RootStackParamList>()
```

## List Rendering

Use **FlashList** over FlatList/ScrollView for large lists:

```typescript
import { FlashList } from '@shopify/flash-list'

<FlashList
  data={items}
  renderItem={({ item }) => <ItemCard item={item} />}
  estimatedItemSize={80}
  keyExtractor={(item) => item.id}
/>
```

## Offline-First

Design for intermittent connectivity:

```typescript
import NetInfo from '@react-native-community/netinfo'

// 1. Local-first: read/write to local storage, sync when online
// 2. Queue mutations: store pending changes, flush on reconnect
// 3. Optimistic updates: update UI immediately, reconcile on sync
```

Storage options by use case:

| Use Case | Library |
|---|---|
| Key-value (fast, sync) | `react-native-mmkv` |
| Key-value (async) | `@react-native-async-storage/async-storage` |
| Structured data / queries | `WatermelonDB`, `Realm` |
| Sensitive data | `expo-secure-store`, `react-native-keychain` |

## OTA Updates

Use **Expo Updates** or **CodePush** for over-the-air JS bundle updates:

```typescript
import * as Updates from 'expo-updates'

async function checkForUpdate(): Promise<void> {
  try {
    const update = await Updates.checkForUpdateAsync()
    if (update.isAvailable) {
      await Updates.fetchUpdateAsync()
      // Consider: prompt user before reloading
      await Updates.reloadAsync()
    }
  } catch (error) {
    // Log but don't crash — updates are non-critical
    console.warn('Update check failed:', error)
  }
}
```

## Deep Linking

Configure deep links with URL scheme and universal links:

```typescript
// app.config.ts (Expo)
export default {
  scheme: 'myapp',
  ios: {
    associatedDomains: ['applinks:example.com'],
  },
  android: {
    intentFilters: [
      {
        action: 'VIEW',
        data: [{ scheme: 'https', host: 'example.com', pathPrefix: '/app' }],
      },
    ],
  },
}
```

## Platform Branching Pattern

```typescript
import { Platform } from 'react-native'

// For behavior differences
function getHapticFeedback(): void {
  if (Platform.OS === 'ios') {
    // iOS-specific haptic
  }
  // Android: no-op or different implementation
}

// For component differences: use .ios.tsx / .android.tsx file extensions
```

## Expo CNG (Continuous Native Generation)

Expo CNG generates `ios/` and `android/` directories on demand. They are NOT committed to git.

### Project Structure

```
app.config.ts        # Single source of truth for native configuration
package.json
src/
e2e/                 # Maestro flows
.gitignore           # Must include ios/ and android/
```

### .gitignore

```
# Expo CNG — native dirs are generated, not committed
ios/
android/
```

### app.config.ts

All native configuration lives here — NOT in Xcode or Gradle files:

```typescript
import { ExpoConfig, ConfigContext } from 'expo/config'

export default ({ config }: ConfigContext): ExpoConfig => ({
  ...config,
  name: 'MyApp',
  slug: 'my-app',
  scheme: 'myapp',
  ios: {
    bundleIdentifier: 'com.example.myapp',
    supportsTablet: true,
  },
  android: {
    package: 'com.example.myapp',
    adaptiveIcon: {
      foregroundImage: './assets/adaptive-icon.png',
      backgroundColor: '#ffffff',
    },
  },
  plugins: [
    // Config Plugins for native customization
    'expo-router',
    'expo-secure-store',
    ['expo-camera', { cameraPermission: 'Allow $(PRODUCT_NAME) to access your camera.' }],
  ],
})
```

### Config Plugins

For native customization that `app.config.ts` doesn't cover, use Config Plugins instead of editing Xcode/Gradle directly:

```typescript
import { ConfigPlugin, withInfoPlist } from 'expo/config-plugins'

// Config Plugins use mutation by design (Expo convention)
const withCustomConfig: ConfigPlugin = (config) => {
  return withInfoPlist(config, (config) => {
    config.modResults.NSLocationWhenInUseUsageDescription = 'Required for maps'
    return config
  })
}
```

### Build Commands

```bash
# Development
npx expo start              # Start Metro dev server
npx expo run:ios            # Build and run on iOS Simulator
npx expo run:android        # Build and run on Android Emulator

# Production (EAS Build)
eas build --platform ios     # Build iOS binary
eas build --platform android # Build Android binary

# OTA Updates
eas update                   # Push JS bundle update

# Verify build (CI)
npx expo export              # Export JS bundle (quick validation)
```

## Reference

- See skill: `react-native-patterns` for component composition, compound components, navigation, state management, forms, error boundaries, gestures, bottom sheets, animations, and accessibility patterns
- See skill: `react-native-best-practices` for performance patterns (FlashList, Reanimated, Turbo Modules)
- See skill: `ios-design` for Apple HIG compliance
- See skill: `android-design` for Material Design 3 compliance
