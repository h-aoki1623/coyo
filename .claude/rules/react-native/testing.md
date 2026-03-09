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

Use **Maestro** for end-to-end testing on simulators/emulators.

- Playwright is for web only and does NOT apply to React Native
- Use **mobile-e2e-tester** agent for mobile E2E tests
- Maestro uses YAML-based declarative flows — no programming language required
- Same flow files run on both iOS and Android

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

### Running Maestro Tests

```bash
# Run a single flow
maestro test e2e/flows/auth/login.yaml

# Run all flows
maestro test e2e/flows/

# Interactive mode (build flows step-by-step)
maestro studio
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
