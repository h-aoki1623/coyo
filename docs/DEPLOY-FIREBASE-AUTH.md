# Firebase Authentication — Production Deployment Guide

Step-by-step guide for deploying Firebase Authentication to production.
This supplements the main [DEPLOY.md](./DEPLOY.md) with auth-specific setup.

## Prerequisites

- [DEPLOY.md](./DEPLOY.md) Phases 1–4 completed
- GCP project created and Cloud Run service running

---

## Phase A: Firebase Project Setup

### A.1 Create Firebase Project

```bash
# Add Firebase to your existing GCP project (recommended)
# In Firebase Console (https://console.firebase.google.com):
# 1. "Add project" → select your existing GCP project
# 2. Google Analytics is optional (disable if not needed)
```

### A.2 Enable Authentication Providers

In Firebase Console > Authentication > Sign-in method, enable:

| Provider | Configuration |
|----------|--------------|
| **Email/Password** | Enable only (email link sign-in not needed) |
| **Google** | Enable → Web Client ID is auto-generated |
| **Apple** | Enable → configure Services ID / Team ID / Key ID / Private Key |

### A.3 Configure Apple Sign-In

In Apple Developer Portal (https://developer.apple.com):

1. **Add Sign In with Apple capability** to your App ID
   - App ID: `to.coyo.app`
2. **Create a Services ID**
   - Identifier: `to.coyo.app.signin` (enter this in Firebase Console)
   - Return URL: set to the Callback URL shown in Firebase Console
3. **Create a Key**
   - Enable Sign In with Apple
   - Download Key ID and Private Key (.p8 file)
4. Enter the following in Firebase Console's Apple provider settings:
   - Services ID: `to.coyo.app.signin`
   - Apple Team ID: `4535US4KHP`
   - Key ID: the Key ID you created
   - Private Key: contents of the .p8 file

### A.4 Download Firebase Config Files

In Firebase Console > Project settings > General:

1. **Add iOS app**
   - Bundle ID: `to.coyo.app`
   - Download `GoogleService-Info.plist` → place at `apps/mobile/GoogleService-Info.plist`
2. **Add Android app**
   - Package name: `to.coyo.app`
   - Register SHA-1 fingerprints for both debug and production (see below)
   - Download `google-services.json` → place at `apps/mobile/google-services.json`

### A.5 Register Android SHA-1 Fingerprints

```bash
# Debug (local development)
keytool -list -v -keystore ~/.android/debug.keystore \
  -alias androiddebugkey -storepass android -keypass android 2>/dev/null | grep SHA1

# Production (EAS Build keystore)
# Managed by EAS Build credentials. Check with:
eas credentials --platform android
# Register the displayed SHA-1 in Firebase Console
```

### A.6 Note the Google Web Client ID

Find it in Firebase Console > Authentication > Sign-in method > Google.
Alternatively, check `google-services.json` under `oauth_client` where `client_type: 3`.

---

## Phase B: Backend Configuration

### B.1 Add Environment Variables

Add the following environment variable to Cloud Run:

| Variable | Value | Description |
|----------|-------|-------------|
| `FIREBASE_PROJECT_ID` | Your Firebase project ID | Used to initialize Firebase Admin SDK |

```bash
gcloud run services update <your-service-name> \
  --region asia-northeast1 \
  --set-env-vars "FIREBASE_PROJECT_ID=<your-firebase-project-id>"
```

> **Note**: Cloud Run automatically provides Application Default Credentials (ADC), so a service account key file is not needed. `FIREBASE_SERVICE_ACCOUNT_PATH` is not required.

### B.2 Grant IAM Permissions

Grant the Cloud Run service account permission to use Firebase Admin SDK:

```bash
PROJECT_ID="<your-project-id>"
PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format='value(projectNumber)')
SA_EMAIL="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# Firebase Auth admin permission (required for token verification)
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/firebase.sdkAdminServiceAgent"
```

### B.3 Run Database Migrations

Run migrations to add authentication columns:

```bash
cd apps/api

# Migration 0003: Add Firebase auth columns (auth_uid, email, display_name, auth_provider)
# Migration 0004: Drop device_id column, make auth_uid NOT NULL
DATABASE_URL='<production-database-url>' \
REDIS_URL='redis://localhost:6379' \
OPENAI_API_KEY='dummy' \
alembic upgrade head
```

> **Warning**: Migration 0004 deletes user records that only have a device_id (no Firebase UID).
> This is designed for pre-release deployment (no production users yet).
> If production users already exist, complete device-ID → Firebase migration first.

### B.4 Update CI/CD Workflow

Add `FIREBASE_PROJECT_ID` to the GitHub Actions deployment workflow.

Add to GitHub repository variables (Settings > Secrets and variables > Actions > Variables):

| Variable | Value |
|----------|-------|
| `FIREBASE_PROJECT_ID` | Your Firebase project ID |

Update the `env_vars` section in `.github/workflows/deploy-api.yml`:

```yaml
env_vars: |
  ENVIRONMENT=production
  GCS_BUCKET_NAME=${{ vars.GCS_BUCKET_NAME }}
  RATE_LIMIT_PER_MINUTE=30
  CORS_ALLOWED_ORIGINS=${{ vars.CORS_ALLOWED_ORIGINS || '[]' }}
  FIREBASE_PROJECT_ID=${{ vars.FIREBASE_PROJECT_ID }}
```

---

## Phase C: Mobile App Configuration

### C.1 Place Firebase Config Files

Firebase config files (`google-services.json`, `GoogleService-Info.plist`) must be available at build time. Use separate Firebase projects for development and production environments.

> **TODO**: Per-environment config file management via EAS Build is tracked in [TODO-FIREBASE-AUTH.md #11](./TODO-FIREBASE-AUTH.md). The steps below describe the interim approach using local file placement.

**Current approach (development):**

Place the config files directly in `apps/mobile/` (they are gitignored):

```
apps/mobile/google-services.json       # Android
apps/mobile/GoogleService-Info.plist    # iOS
```

**Production approach (EAS Build):**

Store production config files as Base64-encoded EAS Secrets and decode at build time:

```bash
cd apps/mobile

# Base64-encode and store GoogleService-Info.plist as EAS Secret
base64 -i GoogleService-Info.plist | eas secret:create \
  --name GOOGLE_SERVICES_PLIST_BASE64 \
  --scope project --force

# Base64-encode and store google-services.json as EAS Secret
base64 -i google-services.json | eas secret:create \
  --name GOOGLE_SERVICES_JSON_BASE64 \
  --scope project --force
```

Decode and place files using a custom EAS Build pre-install hook (e.g., `eas-build-pre-install.sh`).

> **Note**: While these files contain only public information (no secrets), using separate Firebase projects per environment ensures proper isolation of user data and auth state.

### C.2 Add EAS Secrets

```bash
cd apps/mobile

# Google Web Client ID (required for Google Sign-In)
eas secret:create --name GOOGLE_WEB_CLIENT_ID \
  --value "<web-client-id>" --scope project

# iOS Google Client ID (CLIENT_ID from GoogleService-Info.plist)
eas secret:create --name GID_CLIENT_ID \
  --value "<ios-client-id>" --scope project
```

### C.3 Update eas.json

Add environment variables to preview / production profiles:

```json
{
  "build": {
    "preview": {
      "env": {
        "APP_ENV": "staging",
        "API_BASE_URL": "https://<your-cloud-run-url>",
        "GOOGLE_WEB_CLIENT_ID": "<web-client-id>",
        "GID_CLIENT_ID": "<ios-client-id>"
      }
    },
    "production": {
      "env": {
        "APP_ENV": "production",
        "API_BASE_URL": "https://<your-cloud-run-url>",
        "GOOGLE_WEB_CLIENT_ID": "<web-client-id>",
        "GID_CLIENT_ID": "<ios-client-id>"
      }
    }
  }
}
```

> **Note**: When using EAS Secrets, explicit values in `eas.json` are not required (Secrets take precedence). If you do add them to `eas.json`, ensure they are public information only (OAuth Client IDs are public, so this is safe).

### C.4 Build and Test

```bash
cd apps/mobile

# Preview builds (internal testing)
npx eas build --platform ios --profile preview
npx eas build --platform android --profile preview

# Verify authentication flows via TestFlight / internal test track
```

---

## Phase D: Verification Checklist

### Backend

- [ ] `FIREBASE_PROJECT_ID` is set on Cloud Run
- [ ] Cloud Run service account has `roles/firebase.sdkAdminServiceAgent`
- [ ] Migrations 0003 and 0004 applied to production database
- [ ] `/health` returns `{"status":"ok"}`
- [ ] `POST /api/auth/session` with valid Firebase token returns 200
- [ ] `POST /api/auth/session` with invalid token returns 401
- [ ] Protected endpoints (e.g., `/api/conversations`) return 401 without token

### Mobile (iOS)

- [ ] Welcome screen is displayed
- [ ] Email/password sign-up → email verification screen → verify → home screen
- [ ] Google sign-in → home screen
- [ ] Apple sign-in → home screen
- [ ] Sign out → returns to Welcome screen
- [ ] User record is created in the backend database

### Mobile (Android)

- [ ] Welcome screen is displayed
- [ ] Email/password sign-up → email verification screen → verify → home screen
- [ ] Google sign-in → home screen
- [ ] Apple button is NOT shown (not supported on Android)
- [ ] Sign out → returns to Welcome screen

### Email Verification

- [ ] Verification email is sent after sign-up
- [ ] Tapping link in email → browser → `/api/auth/app-redirect` → app opens
- [ ] "Resend" button sends a new verification email
- [ ] After verification, app navigates to home screen

---

## Troubleshooting

### Firebase Initialization Error

**Symptom**: Cloud Run logs show `firebase_init_skipped`

**Fix**:
1. Verify `FIREBASE_PROJECT_ID` is correctly set
2. Check that the service account has `roles/firebase.sdkAdminServiceAgent`
3. Confirm Authentication API is enabled in the Firebase project

### Google Sign-In Failure (Android)

**Symptom**: `DEVELOPER_ERROR` after selecting Google account

**Fix**:
1. Verify the correct SHA-1 fingerprint is registered in Firebase Console
2. Re-download `google-services.json` and rebuild
3. For EAS Build: check that the EAS Build keystore SHA-1 is registered in Firebase

### Apple Sign-In Failure (iOS)

**Symptom**: Error after Apple ID authentication

**Fix**:
1. Verify Apple provider settings in Firebase Console (Services ID, Team ID, Key ID, Private Key)
2. Check that the Services ID Return URL in Apple Developer Portal is correct
3. Confirm `app.config.ts` has `com.apple.developer.applesignin` in entitlements

### Email Verification Redirect Not Working

**Symptom**: Tapping the verification link does not return to the app

**Fix**:
1. Verify `API_BASE_URL` points to the production URL
2. Access `/api/auth/app-redirect` in a browser and confirm it redirects to `coyo://email-verified`
3. iOS: check `scheme: 'coyo'` is set in `app.config.ts`
4. Android: check deep link intent filter configuration

### 401 Unauthorized

**Symptom**: API returns 401 despite being authenticated

**Fix**:
1. Check if the Firebase ID token has expired (valid for 1 hour)
2. Look for `firebase_token_verification_failed` in Cloud Run logs
3. Check if the user is disabled in Firebase Console
