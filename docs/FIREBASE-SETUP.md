# Firebase Setup Guide

This guide covers how to set up Firebase Authentication for local development, E2E testing, and production.

## Environment Strategy

| Environment | Firebase Project | Purpose |
|-------------|-----------------|---------|
| development / E2E | dev project | Local development, CI, E2E tests |
| production | prod project | Production release |

Each environment uses a separate Firebase project to prevent test data from polluting production.

## Prerequisites

- [Firebase Console](https://console.firebase.google.com) access
- [Apple Developer](https://developer.apple.com) account (for Apple Sign-In)
- Expo CLI and EAS CLI installed

---

## Step 1: Create Firebase Project

1. Go to [Firebase Console](https://console.firebase.google.com)
2. Click **Add project** (or use an existing GCP project)
3. Give it a descriptive name (e.g., `<app>-dev` for development, `<app>-prod` for production)
4. Enable Google Analytics if desired (optional)
5. Click **Create project**

## Step 2: Enable Authentication Providers

Go to **Authentication** > **Sign-in method** and enable:

### Email/Password

1. Click **Email/Password**
2. Toggle **Enable** on
3. Leave **Email link (passwordless sign-in)** off
4. Click **Save**

### Google

1. Click **Google**
2. Toggle **Enable** on
3. Set **Public-facing name for project** to your app name
4. Select a **Support email**
5. Click **Save**
6. Note the **Web client ID** that is auto-generated (visible after saving under **Web SDK configuration**). It looks like `<number>-<hash>.apps.googleusercontent.com`

### Apple

1. Click **Apple**
2. Toggle **Enable** on
3. Leave all fields empty (Services ID, Apple team Id, Key Id, Private key are only required for web-based Apple Sign-In, not native iOS)
4. Click **Save**

## Step 3: Register iOS App

1. Go to **Project Settings** (gear icon) > **General** > **Your apps**
2. Click **Add app** > **iOS**
3. Enter bundle ID: the value from `app.config.ts > ios.bundleIdentifier`
4. Enter app nickname (optional)
5. Click **Register app**
6. Download `GoogleService-Info.plist`
7. Place it at: `apps/mobile/GoogleService-Info.plist`

## Step 4: Register Android App

1. In the same **Your apps** section, click **Add app** > **Android**
2. Enter package name: the value from `app.config.ts > android.package`
3. Enter app nickname (optional)
4. Skip SHA-1 for now (required later for production Google Sign-In on Android)
5. Click **Register app**
6. Download `google-services.json`
7. Place it at: `apps/mobile/google-services.json`

## Step 5: Configure Apple Sign-In (iOS)

### Apple Developer Portal

1. Go to [Apple Developer](https://developer.apple.com) > **Certificates, Identifiers & Profiles**
2. Click **Identifiers** > select the App ID matching `app.config.ts > ios.bundleIdentifier`
3. Under **Capabilities**, check **Sign In with Apple**
4. Click **Save**

> **Note**: If the App ID doesn't exist yet, Expo CNG will create it automatically on first build. After it's created, come back and enable Sign In with Apple.

## Step 6: Configure Environment Variables

### Local Development

Set the following environment variables (e.g., in your shell profile or `.env.local`):

```bash
# Firebase project ID (from Firebase Console > Project Settings)
FIREBASE_PROJECT_ID=<your-firebase-project-id>

# Google Web Client ID (from Step 2 > Google provider)
GOOGLE_WEB_CLIENT_ID=<your-web-client-id>.apps.googleusercontent.com
```

### Backend (`apps/api`)

The backend uses **Application Default Credentials (ADC)** for Firebase Admin SDK:

```bash
# Option A: Use gcloud CLI (recommended for local development)
gcloud auth application-default login

# Option B: Service account key (for CI/production)
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json

# Set Firebase project ID in backend config
export FIREBASE_PROJECT_ID=<your-firebase-project-id>
```

### Mobile (`apps/mobile`)

The Google Web Client ID is passed via `app.config.ts > extra.googleWebClientId`:

```bash
export GOOGLE_WEB_CLIENT_ID=<your-web-client-id>.apps.googleusercontent.com
```

Or set it in `apps/mobile/eas.local.json` for EAS Build:

```json
{
  "build": {
    "development": {
      "env": {
        "GOOGLE_WEB_CLIENT_ID": "<your-web-client-id>.apps.googleusercontent.com"
      }
    }
  }
}
```

## Step 7: Install Native Dependencies and Build

```bash
cd apps/mobile

# Install npm packages (includes Firebase native SDKs)
npm install

# Build and run on iOS Simulator
npx expo run:ios

# Build and run on Android Emulator
npx expo run:android
```

## Step 8: Verify Setup

1. Launch the app -- you should see the Welcome screen
2. Tap **Sign Up with Email** -- enter credentials, verify email flow
3. Tap **Sign In with Google** -- Google consent screen should appear
4. Tap **Sign In with Apple** -- Apple Face ID / password prompt should appear (iOS only)

---

## File Locations

| File | Location | Git tracked |
|------|----------|-------------|
| iOS Firebase config | `apps/mobile/GoogleService-Info.plist` | No (gitignored) |
| Android Firebase config | `apps/mobile/google-services.json` | No (gitignored) |
| App config (plugins) | `apps/mobile/app.config.ts` | Yes |
| EAS local overrides | `apps/mobile/eas.local.json` | No (gitignored) |
| Backend Firebase service | `apps/api/src/coyo/services/firebase.py` | Yes |
| Backend config | `apps/api/src/coyo/config.py` | Yes |

## Switching Environments

Firebase config files (`GoogleService-Info.plist`, `google-services.json`) are **per-environment** and **gitignored**. To switch environments:

1. Replace the config files with ones from the target Firebase project
2. Update `FIREBASE_PROJECT_ID` and `GOOGLE_WEB_CLIENT_ID` env vars
3. Rebuild the native app (`npx expo run:ios` / `npx expo run:android`)

For EAS Build, use build profiles in `eas.json` with environment-specific secrets configured in [EAS Secrets](https://docs.expo.dev/build-reference/variables/).

## Production Checklist

Before releasing to production:

- [ ] Create separate production Firebase project
- [ ] Register iOS and Android apps with production bundle ID / package name
- [ ] Add SHA-1 fingerprint for Android (required for production Google Sign-In)
- [ ] Configure Apple Sign-In Service ID in Firebase (if adding web support)
- [ ] Set up EAS Secrets for production `GOOGLE_WEB_CLIENT_ID` and `FIREBASE_PROJECT_ID`
- [ ] Upload production `GoogleService-Info.plist` and `google-services.json` to EAS Secrets
- [ ] Enable App Check in Firebase Console (recommended for production)
- [ ] Set up Firebase Authentication usage alerts and quotas
