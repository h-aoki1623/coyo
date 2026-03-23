---
name: react-native-patterns
description: React Native development patterns for component composition, navigation, gestures, bottom sheets, forms, state management, animations, and mobile accessibility using RN primitives.
---

# React Native Development Patterns

Mobile-first patterns for building production React Native applications with Expo.

## Component Patterns

### Composition Over Inheritance

```typescript
import { View, Text, StyleSheet } from 'react-native'

interface CardProps {
  children: React.ReactNode
  variant?: 'default' | 'outlined'
}

export function Card({ children, variant = 'default' }: CardProps) {
  return (
    <View style={[styles.card, variant === 'outlined' && styles.cardOutlined]}>
      {children}
    </View>
  )
}

export function CardHeader({ children }: { children: React.ReactNode }) {
  return <View style={styles.cardHeader}>{children}</View>
}

export function CardBody({ children }: { children: React.ReactNode }) {
  return <View style={styles.cardBody}>{children}</View>
}

// Usage
<Card variant="outlined">
  <CardHeader><Text style={styles.title}>Title</Text></CardHeader>
  <CardBody><Text>Content</Text></CardBody>
</Card>

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
  },
  cardOutlined: {
    backgroundColor: 'transparent',
    borderWidth: 1,
    borderColor: '#e0e0e0',
  },
  cardHeader: {
    marginBottom: 8,
  },
  cardBody: {
    flex: 1,
  },
  title: {
    fontSize: 18,
    fontWeight: '600',
  },
})
```

### Compound Components

```typescript
import { createContext, useContext, useState } from 'react'
import { View, Text, Pressable, StyleSheet } from 'react-native'

interface TabsContextValue {
  activeTab: string
  setActiveTab: (tab: string) => void
}

const TabsContext = createContext<TabsContextValue | undefined>(undefined)

function useTabsContext() {
  const context = useContext(TabsContext)
  if (!context) throw new Error('Tab components must be used within Tabs')
  return context
}

export function Tabs({ children, defaultTab }: {
  children: React.ReactNode
  defaultTab: string
}) {
  const [activeTab, setActiveTab] = useState(defaultTab)

  return (
    <TabsContext.Provider value={{ activeTab, setActiveTab }}>
      <View>{children}</View>
    </TabsContext.Provider>
  )
}

export function TabList({ children }: { children: React.ReactNode }) {
  return <View style={styles.tabList}>{children}</View>
}

export function Tab({ id, children }: { id: string; children: React.ReactNode }) {
  const { activeTab, setActiveTab } = useTabsContext()
  const isActive = activeTab === id

  return (
    <Pressable
      style={[styles.tab, isActive && styles.tabActive]}
      onPress={() => setActiveTab(id)}
      accessibilityRole="tab"
      accessibilityState={{ selected: isActive }}
    >
      <Text style={[styles.tabText, isActive && styles.tabTextActive]}>
        {children}
      </Text>
    </Pressable>
  )
}

export function TabPanel({ id, children }: { id: string; children: React.ReactNode }) {
  const { activeTab } = useTabsContext()
  if (activeTab !== id) return null
  return <View style={styles.tabPanel}>{children}</View>
}

// Usage
<Tabs defaultTab="overview">
  <TabList>
    <Tab id="overview">Overview</Tab>
    <Tab id="details">Details</Tab>
  </TabList>
  <TabPanel id="overview"><OverviewContent /></TabPanel>
  <TabPanel id="details"><DetailsContent /></TabPanel>
</Tabs>

const styles = StyleSheet.create({
  tabList: {
    flexDirection: 'row',
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  tab: {
    paddingVertical: 12,
    paddingHorizontal: 16,
  },
  tabActive: {
    borderBottomWidth: 2,
    borderBottomColor: '#007AFF',
  },
  tabText: {
    fontSize: 14,
    color: '#666',
  },
  tabTextActive: {
    color: '#007AFF',
    fontWeight: '600',
  },
  tabPanel: {
    padding: 16,
  },
})
```

### Render Props Pattern

```typescript
import { useState, useEffect } from 'react'
import { ActivityIndicator, View, Text } from 'react-native'

interface DataLoaderProps<T> {
  fetcher: () => Promise<T>
  children: (data: T | null, loading: boolean, error: Error | null) => React.ReactNode
}

export function DataLoader<T>({ fetcher, children }: DataLoaderProps<T>) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    let cancelled = false

    fetcher()
      .then(result => { if (!cancelled) setData(result) })
      .catch(err => { if (!cancelled) setError(err) })
      .finally(() => { if (!cancelled) setLoading(false) })

    return () => { cancelled = true }
  }, [fetcher])

  return <>{children(data, loading, error)}</>
}

// Usage
<DataLoader<Market[]> fetcher={fetchMarkets}>
  {(markets, loading, error) => {
    if (loading) return <ActivityIndicator />
    if (error) return <Text>Error: {error.message}</Text>
    return <MarketList markets={markets!} />
  }}
</DataLoader>
```

## Custom Hooks Patterns

### useAppState

```typescript
import { useState, useEffect, useRef } from 'react'
import { AppState, type AppStateStatus } from 'react-native'

export function useAppState(): AppStateStatus {
  const [appState, setAppState] = useState(AppState.currentState)

  useEffect(() => {
    const subscription = AppState.addEventListener('change', setAppState)
    return () => subscription.remove()
  }, [])

  return appState
}

// Track foreground/background transitions
export function useOnForeground(callback: () => void): void {
  const appState = useAppState()
  const prevState = useRef(appState)

  useEffect(() => {
    if (prevState.current !== 'active' && appState === 'active') {
      callback()
    }
    prevState.current = appState
  }, [appState, callback])
}

// Usage: refresh data when app returns to foreground
useOnForeground(() => {
  refetchUserProfile()
})
```

### useNetworkStatus

```typescript
import { useState, useEffect } from 'react'
import NetInfo, { type NetInfoState } from '@react-native-community/netinfo'

interface NetworkStatus {
  isConnected: boolean
  isInternetReachable: boolean | null
  type: string
}

export function useNetworkStatus(): NetworkStatus {
  const [status, setStatus] = useState<NetworkStatus>({
    isConnected: true,
    isInternetReachable: null,
    type: 'unknown',
  })

  useEffect(() => {
    const unsubscribe = NetInfo.addEventListener((state: NetInfoState) => {
      setStatus({
        isConnected: state.isConnected ?? false,
        isInternetReachable: state.isInternetReachable,
        type: state.type,
      })
    })
    return unsubscribe
  }, [])

  return status
}

// Usage
const { isConnected } = useNetworkStatus()
if (!isConnected) {
  return <OfflineBanner />
}
```

### useKeyboardHeight

```typescript
import { useState, useEffect } from 'react'
import { Keyboard, Platform } from 'react-native'

export function useKeyboardHeight(): number {
  const [keyboardHeight, setKeyboardHeight] = useState(0)

  useEffect(() => {
    const showEvent = Platform.OS === 'ios' ? 'keyboardWillShow' : 'keyboardDidShow'
    const hideEvent = Platform.OS === 'ios' ? 'keyboardWillHide' : 'keyboardDidHide'

    const showSub = Keyboard.addListener(showEvent, (e) => {
      setKeyboardHeight(e.endCoordinates.height)
    })
    const hideSub = Keyboard.addListener(hideEvent, () => {
      setKeyboardHeight(0)
    })

    return () => {
      showSub.remove()
      hideSub.remove()
    }
  }, [])

  return keyboardHeight
}
```

### useDebouncedSearch

```typescript
import { useState, useEffect, useCallback } from 'react'
import { TextInput, View, StyleSheet } from 'react-native'

function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])

  return debouncedValue
}

// Usage with TextInput
export function SearchBar({ onSearch }: { onSearch: (query: string) => void }) {
  const [query, setQuery] = useState('')
  const debouncedQuery = useDebounce(query, 300)

  useEffect(() => {
    if (debouncedQuery) {
      onSearch(debouncedQuery)
    }
  }, [debouncedQuery, onSearch])

  return (
    <TextInput
      style={styles.searchInput}
      value={query}
      onChangeText={setQuery}
      placeholder="Search..."
      returnKeyType="search"
      autoCorrect={false}
    />
  )
}

const styles = StyleSheet.create({
  searchInput: {
    height: 44,
    borderRadius: 8,
    backgroundColor: '#f0f0f0',
    paddingHorizontal: 16,
    fontSize: 16,
  },
})
```

See skill: `frontend-patterns` for generic hooks (`useToggle`, `useQuery`) that work cross-platform.

## Navigation Patterns

### Typed Navigation with Expo Router

```typescript
// app/user/[id].tsx
import { useLocalSearchParams, router } from 'expo-router'
import { View, Text, Pressable } from 'react-native'

export default function UserDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>()

  return (
    <View>
      <Text>User: {id}</Text>
      <Pressable onPress={() => router.push({ pathname: '/user/[id]/edit', params: { id } })}>
        <Text>Edit</Text>
      </Pressable>
    </View>
  )
}
```

### Nested Stack + Tab Layout

```
app/
  _layout.tsx           # Root layout (Stack)
  (tabs)/
    _layout.tsx         # Tab navigator
    home/
      _layout.tsx       # Stack within Home tab
      index.tsx         # Home screen
      [id].tsx          # Detail screen
    settings/
      _layout.tsx       # Stack within Settings tab
      index.tsx         # Settings screen
```

```typescript
// app/(tabs)/_layout.tsx
import { Tabs } from 'expo-router'
import { Ionicons } from '@expo/vector-icons'

export default function TabLayout() {
  return (
    <Tabs screenOptions={{ headerShown: false }}>
      <Tabs.Screen
        name="home"
        options={{
          title: 'Home',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="home-outline" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title: 'Settings',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="settings-outline" size={size} color={color} />
          ),
        }}
      />
    </Tabs>
  )
}
```

### Auth-Gated Navigation

```typescript
// app/_layout.tsx
import { Redirect, Stack } from 'expo-router'
import { useAuth } from '@/hooks/useAuth'

export default function RootLayout() {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) return <SplashScreen />

  return (
    <Stack screenOptions={{ headerShown: false }}>
      {isAuthenticated ? (
        <Stack.Screen name="(tabs)" />
      ) : (
        <Stack.Screen name="(auth)" />
      )}
    </Stack>
  )
}

// Protect individual screens with Redirect
export default function ProtectedScreen() {
  const { isAuthenticated } = useAuth()
  if (!isAuthenticated) return <Redirect href="/login" />

  return <ProtectedContent />
}
```

See rules: `react-native/patterns.md` for Expo Router vs React Navigation setup and deep linking configuration.

## State Management Patterns

### Context + Reducer

```typescript
import { createContext, useContext, useReducer, type Dispatch } from 'react'

interface State {
  items: Item[]
  selectedItem: Item | null
  loading: boolean
}

type Action =
  | { type: 'SET_ITEMS'; payload: Item[] }
  | { type: 'SELECT_ITEM'; payload: Item }
  | { type: 'SET_LOADING'; payload: boolean }

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'SET_ITEMS':
      return { ...state, items: action.payload }
    case 'SELECT_ITEM':
      return { ...state, selectedItem: action.payload }
    case 'SET_LOADING':
      return { ...state, loading: action.payload }
    default:
      return state
  }
}

const StoreContext = createContext<{
  state: State
  dispatch: Dispatch<Action>
} | undefined>(undefined)

export function StoreProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(reducer, {
    items: [],
    selectedItem: null,
    loading: false,
  })

  return (
    <StoreContext.Provider value={{ state, dispatch }}>
      {children}
    </StoreContext.Provider>
  )
}

export function useStore() {
  const context = useContext(StoreContext)
  if (!context) throw new Error('useStore must be used within StoreProvider')
  return context
}
```

### Persisted State with MMKV

```typescript
import { MMKV } from 'react-native-mmkv'
import { useState, useCallback } from 'react'

const storage = new MMKV()

export function usePersistedState<T>(
  key: string,
  defaultValue: T
): [T, (value: T | ((prev: T) => T)) => void] {
  const [state, setState] = useState<T>(() => {
    const stored = storage.getString(key)
    return stored ? JSON.parse(stored) as T : defaultValue
  })

  const setPersistedState = useCallback(
    (value: T | ((prev: T) => T)) => {
      setState(prev => {
        const next = typeof value === 'function'
          ? (value as (prev: T) => T)(prev)
          : value
        storage.set(key, JSON.stringify(next))
        return next
      })
    },
    [key]
  )

  return [state, setPersistedState]
}

// Usage
const [theme, setTheme] = usePersistedState<'light' | 'dark'>('theme', 'light')
```

### Offline Mutation Queue

```typescript
import { MMKV } from 'react-native-mmkv'

interface QueuedMutation {
  id: string
  endpoint: string
  method: 'POST' | 'PUT' | 'DELETE'
  body: unknown
  createdAt: number
}

const storage = new MMKV()
const QUEUE_KEY = 'mutation_queue'

function getQueue(): QueuedMutation[] {
  const raw = storage.getString(QUEUE_KEY)
  return raw ? JSON.parse(raw) : []
}

function saveQueue(queue: QueuedMutation[]): void {
  storage.set(QUEUE_KEY, JSON.stringify(queue))
}

export function enqueueMutation(mutation: Omit<QueuedMutation, 'id' | 'createdAt'>): void {
  const queue = getQueue()
  const entry: QueuedMutation = {
    ...mutation,
    id: Math.random().toString(36).slice(2),
    createdAt: Date.now(),
  }
  saveQueue([...queue, entry])
}

export async function flushQueue(): Promise<void> {
  const queue = getQueue()
  const remaining: QueuedMutation[] = []

  for (const mutation of queue) {
    try {
      await fetch(mutation.endpoint, {
        method: mutation.method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(mutation.body),
      })
    } catch {
      remaining.push(mutation)
    }
  }

  saveQueue(remaining)
}

// Trigger flush on reconnect (combine with useNetworkStatus)
```

See skill: `react-native-best-practices` for Jotai/Zustand performance optimization patterns.
See rules: `react-native/patterns.md` for the storage options table.

## Form Handling Patterns

### Controlled Form with Validation

```typescript
import { useState } from 'react'
import { View, Text, TextInput, Pressable, StyleSheet } from 'react-native'

interface FormData {
  name: string
  email: string
}

interface FormErrors {
  name?: string
  email?: string
}

export function CreateItemForm({ onSubmit }: { onSubmit: (data: FormData) => void }) {
  const [formData, setFormData] = useState<FormData>({ name: '', email: '' })
  const [errors, setErrors] = useState<FormErrors>({})

  const validate = (): boolean => {
    const newErrors: FormErrors = {}

    if (!formData.name.trim()) {
      newErrors.name = 'Name is required'
    }
    if (!formData.email.trim()) {
      newErrors.email = 'Email is required'
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = 'Invalid email format'
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSubmit = () => {
    if (validate()) {
      onSubmit(formData)
    }
  }

  return (
    <View style={styles.form}>
      <View style={styles.field}>
        <Text style={styles.label}>Name</Text>
        <TextInput
          style={[styles.input, errors.name && styles.inputError]}
          value={formData.name}
          onChangeText={text => setFormData(prev => ({ ...prev, name: text }))}
          placeholder="Enter name"
          autoCapitalize="words"
        />
        {errors.name && <Text style={styles.errorText}>{errors.name}</Text>}
      </View>

      <View style={styles.field}>
        <Text style={styles.label}>Email</Text>
        <TextInput
          style={[styles.input, errors.email && styles.inputError]}
          value={formData.email}
          onChangeText={text => setFormData(prev => ({ ...prev, email: text }))}
          placeholder="Enter email"
          keyboardType="email-address"
          autoCapitalize="none"
          autoCorrect={false}
        />
        {errors.email && <Text style={styles.errorText}>{errors.email}</Text>}
      </View>

      <Pressable style={styles.submitButton} onPress={handleSubmit}>
        <Text style={styles.submitText}>Submit</Text>
      </Pressable>
    </View>
  )
}

const styles = StyleSheet.create({
  form: { padding: 16, gap: 16 },
  field: { gap: 4 },
  label: { fontSize: 14, fontWeight: '600', color: '#333' },
  input: {
    height: 44,
    borderWidth: 1,
    borderColor: '#ccc',
    borderRadius: 8,
    paddingHorizontal: 12,
    fontSize: 16,
  },
  inputError: { borderColor: '#dc3545' },
  errorText: { fontSize: 12, color: '#dc3545' },
  submitButton: {
    height: 48,
    backgroundColor: '#007AFF',
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  submitText: { color: '#fff', fontSize: 16, fontWeight: '600' },
})
```

### KeyboardAvoidingView Pattern

```typescript
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet } from 'react-native'

export function FormScreen({ children }: { children: React.ReactNode }) {
  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      keyboardVerticalOffset={Platform.OS === 'ios' ? 88 : 0}
    >
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        {children}
      </ScrollView>
    </KeyboardAvoidingView>
  )
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  scrollContent: { flexGrow: 1, padding: 16 },
})
```

See skill: `react-native-best-practices` for `TextInput` performance optimization (uncontrolled patterns).
See rules: `typescript/coding-style.md` for Zod validation patterns.

## Error Boundary Pattern

### Basic Error Boundary

```typescript
import { Component, type ErrorInfo } from 'react'
import { View, Text, Pressable, StyleSheet } from 'react-native'

interface ErrorBoundaryProps {
  children: React.ReactNode
  fallback?: (error: Error, retry: () => void) => React.ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Send to crash reporting service (Sentry, Crashlytics, etc.)
    crashReporter.captureException(error, { extra: errorInfo })
  }

  handleRetry = (): void => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError && this.state.error) {
      if (this.props.fallback) {
        return this.props.fallback(this.state.error, this.handleRetry)
      }

      return (
        <View style={styles.container}>
          <Text style={styles.title}>Something went wrong</Text>
          <Text style={styles.message}>{this.state.error.message}</Text>
          <Pressable style={styles.retryButton} onPress={this.handleRetry}>
            <Text style={styles.retryText}>Try Again</Text>
          </Pressable>
        </View>
      )
    }

    return this.props.children
  }
}

const styles = StyleSheet.create({
  container: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  title: { fontSize: 20, fontWeight: '700', marginBottom: 8 },
  message: { fontSize: 14, color: '#666', textAlign: 'center', marginBottom: 24 },
  retryButton: {
    paddingVertical: 12,
    paddingHorizontal: 24,
    backgroundColor: '#007AFF',
    borderRadius: 8,
  },
  retryText: { color: '#fff', fontSize: 16, fontWeight: '600' },
})
```

### Screen-Level Error Isolation

```typescript
// Wrap individual screens so one crash doesn't take down the entire app
// app/(tabs)/home/_layout.tsx
import { Stack } from 'expo-router'

export default function HomeLayout() {
  return (
    <ErrorBoundary>
      <Stack />
    </ErrorBoundary>
  )
}
```

## Gesture & Bottom Sheet Patterns

### Swipe-to-Delete

```typescript
import { View, Text, Pressable, StyleSheet } from 'react-native'
import { Swipeable } from 'react-native-gesture-handler'

interface SwipeableRowProps {
  children: React.ReactNode
  onDelete: () => void
}

export function SwipeableRow({ children, onDelete }: SwipeableRowProps) {
  const renderRightActions = () => (
    <Pressable style={styles.deleteAction} onPress={onDelete}>
      <Text style={styles.deleteText}>Delete</Text>
    </Pressable>
  )

  return (
    <Swipeable renderRightActions={renderRightActions} overshootRight={false}>
      {children}
    </Swipeable>
  )
}

// Usage
<SwipeableRow onDelete={() => removeItem(item.id)}>
  <ItemCard item={item} />
</SwipeableRow>

const styles = StyleSheet.create({
  deleteAction: {
    backgroundColor: '#dc3545',
    justifyContent: 'center',
    alignItems: 'center',
    width: 80,
  },
  deleteText: {
    color: '#fff',
    fontWeight: '600',
  },
})
```

### Pull-to-Refresh

```typescript
import { useState, useCallback } from 'react'
import { RefreshControl } from 'react-native'
import { FlashList } from '@shopify/flash-list'

export function RefreshableList<T>({ data, renderItem, onRefresh, estimatedItemSize }: {
  data: T[]
  renderItem: ({ item }: { item: T }) => React.ReactElement
  onRefresh: () => Promise<void>
  estimatedItemSize: number
}) {
  const [refreshing, setRefreshing] = useState(false)

  const handleRefresh = useCallback(async () => {
    setRefreshing(true)
    try {
      await onRefresh()
    } finally {
      setRefreshing(false)
    }
  }, [onRefresh])

  return (
    <FlashList
      data={data}
      renderItem={renderItem}
      estimatedItemSize={estimatedItemSize}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={handleRefresh} />
      }
    />
  )
}
```

### Bottom Sheet

```typescript
import { useCallback, useMemo, useRef } from 'react'
import { View, Text, Pressable, StyleSheet } from 'react-native'
import BottomSheet, { BottomSheetBackdrop, type BottomSheetBackdropProps } from '@gorhom/bottom-sheet'

export function OptionsSheet({ onSelect }: {
  onSelect: (option: string) => void
}) {
  const bottomSheetRef = useRef<BottomSheet>(null)
  const snapPoints = useMemo(() => ['25%', '50%'], [])

  const handleOpen = useCallback(() => {
    bottomSheetRef.current?.expand()
  }, [])

  const renderBackdrop = useCallback(
    (props: BottomSheetBackdropProps) => (
      <BottomSheetBackdrop {...props} disappearsOnIndex={-1} appearsOnIndex={0} />
    ),
    []
  )

  return (
    <>
      <Pressable onPress={handleOpen}>
        <Text>Open Options</Text>
      </Pressable>

      <BottomSheet
        ref={bottomSheetRef}
        index={-1}
        snapPoints={snapPoints}
        enablePanDownToClose
        backdropComponent={renderBackdrop}
      >
        <View style={styles.sheetContent}>
          {['Option A', 'Option B', 'Option C'].map(option => (
            <Pressable
              key={option}
              style={styles.sheetOption}
              onPress={() => {
                onSelect(option)
                bottomSheetRef.current?.close()
              }}
            >
              <Text style={styles.sheetOptionText}>{option}</Text>
            </Pressable>
          ))}
        </View>
      </BottomSheet>
    </>
  )
}

const styles = StyleSheet.create({
  sheetContent: { padding: 16 },
  sheetOption: {
    paddingVertical: 16,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#e0e0e0',
  },
  sheetOptionText: { fontSize: 16 },
})
```

See skill: `react-native-best-practices` for gesture-driven animation patterns with Reanimated.
See skill: `ios-design` for Apple HIG gesture conventions.
See skill: `android-design` for Material Design 3 bottom sheet rules.

## Animation Patterns

### Layout Animations (Enter/Exit)

```typescript
import { View, Text, Pressable, StyleSheet } from 'react-native'
import Animated, { FadeIn, FadeOut, SlideInRight, SlideOutLeft } from 'react-native-reanimated'

// List item enter/exit (equivalent to Framer Motion AnimatePresence)
export function AnimatedListItem({ item, onRemove }: {
  item: Item
  onRemove: () => void
}) {
  return (
    <Animated.View
      entering={SlideInRight.duration(300)}
      exiting={SlideOutLeft.duration(200)}
      style={styles.listItem}
    >
      <Text>{item.name}</Text>
      <Pressable onPress={onRemove}>
        <Text>Remove</Text>
      </Pressable>
    </Animated.View>
  )
}

// Screen element fade-in
export function FadeInView({ children, delay = 0 }: {
  children: React.ReactNode
  delay?: number
}) {
  return (
    <Animated.View entering={FadeIn.duration(400).delay(delay)}>
      {children}
    </Animated.View>
  )
}

const styles = StyleSheet.create({
  listItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    padding: 16,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#e0e0e0',
  },
})
```

### Animated Modal

```typescript
import { useEffect } from 'react'
import { Pressable, StyleSheet } from 'react-native'
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withTiming,
  withSpring,
} from 'react-native-reanimated'

export function AnimatedModal({ visible, onClose, children }: {
  visible: boolean
  onClose: () => void
  children: React.ReactNode
}) {
  const opacity = useSharedValue(0)
  const translateY = useSharedValue(50)

  useEffect(() => {
    if (visible) {
      opacity.value = withTiming(1, { duration: 200 })
      translateY.value = withSpring(0, { damping: 20 })
    } else {
      opacity.value = withTiming(0, { duration: 150 })
      translateY.value = withTiming(50, { duration: 150 })
    }
    // opacity and translateY are stable shared value refs
  }, [visible])

  const backdropStyle = useAnimatedStyle(() => ({
    opacity: opacity.value,
  }))

  const contentStyle = useAnimatedStyle(() => ({
    opacity: opacity.value,
    transform: [{ translateY: translateY.value }],
  }))

  if (!visible) return null

  return (
    <>
      <Animated.View style={[styles.backdrop, backdropStyle]}>
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose} />
      </Animated.View>
      <Animated.View style={[styles.modalContent, contentStyle]}>
        {children}
      </Animated.View>
    </>
  )
}

const styles = StyleSheet.create({
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
  },
  modalContent: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: '#fff',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 24,
    minHeight: 200,
  },
})
```

### Skeleton Shimmer

```typescript
import { useEffect } from 'react'
import { View, StyleSheet } from 'react-native'
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withRepeat,
  withTiming,
  Easing,
} from 'react-native-reanimated'

export function Skeleton({ width, height, borderRadius = 4 }: {
  width: number | `${number}%`
  height: number
  borderRadius?: number
}) {
  const opacity = useSharedValue(0.3)

  useEffect(() => {
    // opacity is a stable shared value ref
    opacity.value = withRepeat(
      withTiming(1, { duration: 800, easing: Easing.inOut(Easing.ease) }),
      -1,
      true
    )
  }, [])

  const animatedStyle = useAnimatedStyle(() => ({
    opacity: opacity.value,
  }))

  return (
    <Animated.View
      style={[
        styles.skeleton,
        { width, height, borderRadius },
        animatedStyle,
      ]}
    />
  )
}

// Usage
export function CardSkeleton() {
  return (
    <View style={styles.card}>
      <Skeleton width="60%" height={20} />
      <Skeleton width="100%" height={14} />
      <Skeleton width="80%" height={14} />
    </View>
  )
}

const styles = StyleSheet.create({
  skeleton: { backgroundColor: '#e0e0e0' },
  card: { padding: 16, gap: 8 },
})
```

### Reduce Motion Support

```typescript
import { useEffect, useState } from 'react'
import { AccessibilityInfo } from 'react-native'

export function useReduceMotion(): boolean {
  const [reduceMotion, setReduceMotion] = useState(false)

  useEffect(() => {
    AccessibilityInfo.isReduceMotionEnabled().then(setReduceMotion)

    const subscription = AccessibilityInfo.addEventListener(
      'reduceMotionChanged',
      setReduceMotion
    )
    return () => subscription.remove()
  }, [])

  return reduceMotion
}

// Usage: conditionally disable animations
const reduceMotion = useReduceMotion()

<Animated.View
  entering={reduceMotion ? undefined : FadeIn.duration(300)}
>
  {children}
</Animated.View>
```

See skill: `react-native-best-practices` for Reanimated performance deep-dive (worklets, UI thread, shared values).

## Accessibility Patterns

### Accessible Interactive Components

```typescript
import { Pressable, Text, StyleSheet } from 'react-native'

// Icon-only button with accessibility label
export function IconButton({ icon, label, onPress }: {
  icon: React.ReactNode
  label: string
  onPress: () => void
}) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={styles.iconButton}
    >
      {icon}
    </Pressable>
  )
}

// Toggle with accessibility state
export function ToggleButton({ label, isOn, onToggle }: {
  label: string
  isOn: boolean
  onToggle: () => void
}) {
  return (
    <Pressable
      onPress={onToggle}
      accessibilityRole="switch"
      accessibilityLabel={label}
      accessibilityState={{ checked: isOn }}
      style={[styles.toggle, isOn && styles.toggleOn]}
    >
      <Text style={styles.toggleText}>{isOn ? 'On' : 'Off'}</Text>
    </Pressable>
  )
}

const styles = StyleSheet.create({
  iconButton: {
    minWidth: 44,
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  toggle: {
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 16,
    backgroundColor: '#ccc',
  },
  toggleOn: { backgroundColor: '#34C759' },
  toggleText: { fontWeight: '600' },
})
```

### Dynamic Announcements

```typescript
import { AccessibilityInfo } from 'react-native'

// Announce search results to screen reader (equivalent to ARIA live regions)
function announceSearchResults(count: number): void {
  AccessibilityInfo.announceForAccessibility(
    count === 0
      ? 'No results found'
      : `${count} result${count !== 1 ? 's' : ''} found`
  )
}

// Usage: call after search completes
const results = await performSearch(query)
announceSearchResults(results.length)
```

### Touch Target Sizing

```typescript
import { Pressable, StyleSheet } from 'react-native'

// WRONG: Touch target too small
<Pressable style={{ width: 24, height: 24 }} onPress={onPress}>
  <SmallIcon />
</Pressable>

// CORRECT: Minimum 44pt (iOS) / 48dp (Android) touch target
<Pressable
  style={styles.touchTarget}
  hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
  onPress={onPress}
>
  <SmallIcon />
</Pressable>

const styles = StyleSheet.create({
  touchTarget: {
    minWidth: 44,
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
})
```

See skill: `ios-design` for Apple HIG accessibility rules (VoiceOver, Dynamic Type, Reduce Motion).
See skill: `android-design` for Material Design 3 accessibility rules (TalkBack, touch targets).

## Loading & Empty State Patterns

### Screen State Machine

```typescript
import { View, Text, Pressable, ActivityIndicator, StyleSheet } from 'react-native'

type ScreenState<T> =
  | { status: 'loading' }
  | { status: 'error'; error: Error; retry: () => void }
  | { status: 'empty'; message: string }
  | { status: 'data'; data: T }

export function ScreenStateRenderer<T>({
  state,
  renderData,
  renderSkeleton,
}: {
  state: ScreenState<T>
  renderData: (data: T) => React.ReactNode
  renderSkeleton?: () => React.ReactNode
}) {
  switch (state.status) {
    case 'loading':
      return renderSkeleton ? renderSkeleton() : (
        <View style={styles.center}>
          <ActivityIndicator size="large" />
        </View>
      )
    case 'error':
      return (
        <View style={styles.center}>
          <Text style={styles.errorTitle}>Something went wrong</Text>
          <Text style={styles.errorMessage}>{state.error.message}</Text>
          <Pressable style={styles.retryButton} onPress={state.retry}>
            <Text style={styles.retryText}>Retry</Text>
          </Pressable>
        </View>
      )
    case 'empty':
      return (
        <View style={styles.center}>
          <Text style={styles.emptyTitle}>Nothing here yet</Text>
          <Text style={styles.emptyMessage}>{state.message}</Text>
        </View>
      )
    case 'data':
      return <>{renderData(state.data)}</>
  }
}

// Usage
const [screenState, setScreenState] = useState<ScreenState<Item[]>>({ status: 'loading' })

useEffect(() => {
  fetchItems()
    .then(items =>
      setScreenState(
        items.length > 0
          ? { status: 'data', data: items }
          : { status: 'empty', message: 'Add your first item to get started' }
      )
    )
    .catch(error =>
      setScreenState({ status: 'error', error, retry: () => loadItems() })
    )
}, [])

<ScreenStateRenderer
  state={screenState}
  renderData={items => <ItemList items={items} />}
  renderSkeleton={() => <ItemListSkeleton />}
/>

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  errorTitle: { fontSize: 18, fontWeight: '700', marginBottom: 8 },
  errorMessage: { fontSize: 14, color: '#666', textAlign: 'center', marginBottom: 24 },
  retryButton: {
    paddingVertical: 12,
    paddingHorizontal: 24,
    backgroundColor: '#007AFF',
    borderRadius: 8,
  },
  retryText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  emptyTitle: { fontSize: 18, fontWeight: '600', marginBottom: 8 },
  emptyMessage: { fontSize: 14, color: '#999', textAlign: 'center' },
})
```

**Remember**: React Native patterns bridge React's component model with native mobile conventions. Choose patterns that respect platform idioms while maximizing code sharing.
