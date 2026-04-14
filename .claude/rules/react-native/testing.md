---
paths:
  - "**/*.ts"
  - "**/*.tsx"
  - "**/*.js"
  - "**/*.jsx"
---
# React Native Testing

> This file extends [common/testing.md](../common/testing.md) and [typescript/testing.md](../typescript/testing.md) with React Native specific content.

## Unit & Integration Testing

Use **Jest** + **React Native Testing Library** (`@testing-library/react-native`):

```typescript
import { render, screen, fireEvent } from '@testing-library/react-native'
import { UserProfile } from './UserProfile'

describe('UserProfile', () => {
  it('displays user name', () => {
    render(<UserProfile name="Alice" />)
    expect(screen.getByText('Alice')).toBeTruthy()
  })

  it('calls onEdit when edit button pressed', () => {
    const onEdit = jest.fn()
    render(<UserProfile name="Alice" onEdit={onEdit} />)
    fireEvent.press(screen.getByRole('button', { name: 'Edit' }))
    expect(onEdit).toHaveBeenCalledTimes(1)
  })
})
```

## Native Module Mocking

Mock native modules in `jest.setup.js` or individual test files:

```typescript
// jest.setup.js
jest.mock('react-native/Libraries/Animated/NativeAnimatedHelper')

jest.mock('@react-native-async-storage/async-storage', () =>
  require('@react-native-async-storage/async-storage/jest/async-storage-mock')
)
```

## Navigation Testing

Wrap components in a navigation context for tests:

```typescript
import { NavigationContainer } from '@react-navigation/native'

function renderWithNavigation(component: React.ReactElement) {
  return render(
    <NavigationContainer>{component}</NavigationContainer>
  )
}
```

## E2E Testing

Maestro flow syntax and platform test matrix. For execution rules, see `common/testing.md`.

### Basic Maestro Flow

```yaml
# e2e/flows/auth/login.yaml
appId: com.example.myapp
---
- launchApp
- assertVisible: "Welcome"
- tapOn: "Log In"
- tapOn: "Email"
- inputText: "test@example.com"
- tapOn: "Password"
- inputText: "testpassword123"
- tapOn: "Sign In"
- assertVisible: "Home"
- takeScreenshot: "after-login"
```

### Platform Test Matrix

| Scope | iOS | Android |
|---|---|---|
| Unit / Integration | Jest (shared) | Jest (shared) |
| E2E | Maestro (iOS Simulator) | Maestro (Android Emulator) |
| CI | EAS Workflows (`eas/maestro_test`) | EAS Workflows (`eas/maestro_test`) |
| Device testing | TestFlight / physical device | Internal testing track / physical device |

## Coverage

```bash
jest --coverage --coverageReporters=text-summary
```

## Reference

- See skill: `ts-test-patterns` for Jest patterns and mocking strategies
- See skill: `react-native-best-practices` for RN-specific testing setup and native module mocking
