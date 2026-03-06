# E2E Testing (Maestro)

End-to-end tests for the Coyo mobile app using [Maestro](https://maestro.mobile.dev/).

## Prerequisites

- **Maestro CLI**: `curl -Ls "https://get.maestro.mobile.dev" | bash`
- **iOS**: Xcode with a booted iOS Simulator
- **Android**: Android SDK with a running emulator (4GB+ RAM recommended)
- **Docker**: For Postgres + Redis (backend dependencies)
- **Python venv**: At `apps/api/.venv` for the backend API
- **expo-dev-client**: Must be in `package.json` (`npx expo install expo-dev-client`)

## Running Tests

```bash
# From apps/mobile/
./e2e/run-e2e.sh ios          # iOS only
./e2e/run-e2e.sh android      # Android only
./e2e/run-e2e.sh all          # Both platforms

# Run a single flow manually (requires Metro + backend running)
maestro test e2e/app-launch.yaml
```

`run-e2e.sh` automatically handles: Docker, backend API, Metro bundler, `adb reverse`, Maestro driver APKs, and expo-dev-client dialog dismissal.

## Test Flows

| Flow | Description | Backend Required |
|------|-------------|:---:|
| `app-launch` | Home screen renders with greeting and topics | No |
| `home-topic-cards` | All 5 topic cards + history button visible | No |
| `navigate-to-history` | Home -> History -> Back to Home | Yes |
| `history-empty-state` | History screen loads (empty or with data) | Yes |
| `start-conversation` | Tap topic -> Talk screen appears | Yes |
| `feedback-return-home` | Start -> End -> Feedback -> Home | Yes |
| `voice-conversation` | Full voice flow with E2E test audio | Yes |

## Writing New Flows

### Use `clearState: false`

All flows must use `clearState: false` on `launchApp` to preserve the expo-dev-client onboarding preference. Without this, the dev-client "Continue" dialog appears on every launch and blocks tests.

```yaml
# CORRECT
- launchApp:
    clearState: false

# WRONG - triggers dev-client dialog
- launchApp
```

### Use testID selectors

Prefer `id:` (testID) over `text:` for reliability across platforms and locales.

```yaml
# CORRECT
- tapOn:
    id: "topic-sports"

# FRAGILE - breaks if text changes or locale differs
- tapOn: "Sports"
```

### Cross-platform Alert dialog buttons

Android native AlertDialog auto-uppercases button text ("END" vs "End" on iOS). Maestro cannot find Android native dialog buttons via regex or index. Use `runFlow` with platform conditions:

```yaml
# Android: uppercase "END" (unique on screen, no index needed)
- runFlow:
    when:
      visible: "END"
    commands:
      - tapOn: "END"
# iOS: "End" (may need index to disambiguate from other "End" text)
- runFlow:
    when:
      visible:
        text: "End"
        index: 1
    commands:
      - tapOn:
          text: "End"
          index: 1
```

### Install dependencies via Expo

Always use `npx expo install <package>` instead of `npm install <package>` to ensure Expo SDK version compatibility.

## Troubleshooting

### Android: "Unable to load script" red screen

**Cause**: `expo-dev-client` missing from `package.json`.
**Fix**: `npx expo install expo-dev-client && npx expo prebuild --platform android --clean && npx expo run:android`

### Android: Maestro gRPC connection refused (port 7001)

**Cause**: Maestro driver APKs not installed (lost after `emulator -wipe-data`).
**Fix**: `run-e2e.sh` auto-installs them. Manually:
```bash
jar xf ~/.maestro/lib/maestro-client.jar maestro-server.apk maestro-app.apk
adb install -r maestro-server.apk && adb install -r maestro-app.apk
```

### Android: API/Metro unreachable

**Cause**: `adb reverse` cleared by APK install.
**Fix**: `adb reverse tcp:8081 tcp:8081 && adb reverse tcp:8000 tcp:8000`

### Android: "expo-module-gradle-plugin not found"

**Cause**: Incompatible dependency version (e.g., `expo-localization@17` with SDK 52).
**Fix**: `npx expo install --fix` to auto-correct versions.

### Black screen after launch (Android)

**Cause**: `expo-font` fails silently without `expo-file-system`.
**Fix**: `npx expo install expo-file-system` and handle `fontError` in App.tsx.

### expo-dev-client "Continue" dialog blocks tests

**Cause**: First launch after install shows onboarding dialog.
**Fix**: `run-e2e.sh` auto-dismisses it via `helpers/dismiss-dev-client.yaml`. For manual runs, tap "Continue" once before running Maestro.
