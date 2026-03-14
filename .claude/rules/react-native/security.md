# React Native Security

> This file extends [common/security.md](../common/security.md) and [typescript/security.md](../typescript/security.md) with React Native specific content.

## Sensitive Data Storage

NEVER store secrets in AsyncStorage (unencrypted, readable on rooted devices):

```typescript
// WRONG: AsyncStorage is NOT secure
import AsyncStorage from '@react-native-async-storage/async-storage'
await AsyncStorage.setItem('auth_token', token)  // INSECURE!

// CORRECT: Use Keychain/Keystore via secure storage
import * as SecureStore from 'expo-secure-store'
await SecureStore.setItemAsync('auth_token', token)

// Alternative: react-native-keychain
import * as Keychain from 'react-native-keychain'
await Keychain.setGenericPassword('auth', token)
```

## Certificate Pinning

Pin TLS certificates to prevent MITM attacks:

```typescript
// With react-native-ssl-pinning or TrustKit (iOS) / OkHttp CertificatePinner (Android)
// Configure in native layer for production apps handling sensitive data
```

## Deep Link Validation

ALWAYS validate deep link parameters before processing:

```typescript
// WRONG: Trust deep link input directly
const userId = route.params.userId
navigateToUser(userId)

// CORRECT: Validate and sanitize
const userId = route.params.userId
if (typeof userId === 'string' && /^[a-zA-Z0-9-]+$/.test(userId)) {
  navigateToUser(userId)
}
```

## Biometric Authentication

Use platform biometric APIs for sensitive actions:

```typescript
import * as LocalAuthentication from 'expo-local-authentication'

async function authenticateUser(): Promise<boolean> {
  const hasHardware = await LocalAuthentication.hasHardwareAsync()
  if (!hasHardware) return false

  const result = await LocalAuthentication.authenticateAsync({
    promptMessage: 'Authenticate to continue',
    fallbackLabel: 'Use passcode',
  })
  return result.success
}
```

## Environment Variables

Use Expo constants or `react-native-config` for environment-specific values:

```typescript
// Expo
import Constants from 'expo-constants'
const apiUrl = Constants.expoConfig?.extra?.apiUrl

// react-native-config
import Config from 'react-native-config'
const apiUrl = Config.API_URL
```

NEVER embed API secrets in the JS bundle. Use a backend proxy for sensitive API calls.

## Security Checklist (Mobile-Specific)

Before commit:
- [ ] No secrets in AsyncStorage (use SecureStore/Keychain)
- [ ] No API keys embedded in JS bundle
- [ ] Deep link parameters validated and sanitized
- [ ] Certificate pinning configured for production (if handling sensitive data)
- [ ] Biometric auth for sensitive actions (payments, profile changes)
- [ ] No sensitive data in logs (`console.log`, crash reporters)
- [ ] ProGuard/R8 enabled for Android release builds (code obfuscation)

## Agent Support

- Use **security-reviewer** agent for comprehensive security audits
