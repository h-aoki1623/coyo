# Firebase Authentication — Post-Merge TODOs

Issues to create after the Firebase Auth PR is merged.
These were identified during code review (code-reviewer, security-reviewer, python-reviewer, database-reviewer).

---

## Security / Infrastructure

### 1. Add rate limiting to authentication endpoints
- **Priority**: High
- **Category**: Security / Infrastructure
- **Details**: `rate_limit_per_minute` setting exists in `config.py` but is never applied. The `POST /api/auth/session` endpoint has no rate limiting. An attacker could flood the endpoint causing database connection exhaustion.
- **Action**: Add rate limiting middleware (e.g., `slowapi` for FastAPI) to auth endpoints and other routes.
- **Files**: `apps/api/src/coyo/main.py`, `apps/api/src/coyo/routers/auth.py`

### 2. Restrict CORS origins for production
- **Priority**: High
- **Category**: Security
- **Details**: CORS `allow_origins` defaults to localhost URLs. Production deployments must use explicit HTTPS origins. Add startup validation to reject insecure origins in production.
- **Action**: Add validation in production to ensure CORS origins are HTTPS and not localhost.
- **Files**: `apps/api/src/coyo/middleware.py`, `apps/api/src/coyo/config.py`

### 3. Fail loudly on Firebase initialization failure in production
- **Priority**: High
- **Category**: Security / Reliability
- **Details**: When Firebase initialization fails, the app logs a warning and continues. In production, this means auth is silently broken while `/health` returns ok. Should fail the startup in production.
- **Action**: Raise `RuntimeError` if `FIREBASE_PROJECT_ID` is set but initialization fails in production environment.
- **Files**: `apps/api/src/coyo/services/firebase.py`, `apps/api/src/coyo/main.py`

### 4. Sanitize error messages to prevent information leakage
- **Priority**: Medium
- **Category**: Security
- **Details**: `NotFoundError` includes resource ID in the error message (`f"{resource} not found: {id}"`). `ExternalServiceError` includes service name and detail. These can leak internal identifiers and service details to clients.
- **Action**: Return generic messages to clients, log detailed info server-side only.
- **Files**: `apps/api/src/coyo/exceptions.py`

### 5. Add CSP headers to app-redirect endpoint
- **Priority**: Low
- **Category**: Security
- **Details**: `/api/auth/app-redirect` returns inline HTML without Content-Security-Policy headers. While content is static and risk is low, CSP is a defense-in-depth measure.
- **Action**: Add `Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'` header to the HTML response.
- **Files**: `apps/api/src/coyo/routers/auth.py`

---

## Refactoring

### 6. Extract shared UI components from auth form screens
- **Priority**: Medium
- **Category**: Refactor
- **Details**: `SignUpFormScreen` and `SignInFormScreen` share identical patterns for error container, submit button (with disabled/pressed states), `KeyboardAvoidingView` wrapping, and `SafeAreaView + NavBar + ScrollView` layout. Styles for `errorContainer`, `errorText`, `submitButton`, `submitButtonDisabled`, `submitButtonPressed`, `submitButtonText` are duplicated verbatim.
- **Action**: Extract shared components (e.g., `AuthFormLayout`, `SubmitButton`, `ErrorBanner`).
- **Files**: `apps/mobile/src/features/auth/SignUpFormScreen.tsx`, `apps/mobile/src/features/auth/SignInFormScreen.tsx`

### 7. Use StrEnum for auth_provider
- **Priority**: Low
- **Category**: Refactor
- **Details**: `auth_provider` is a plain string with a CHECK constraint. Using a Python `StrEnum` would provide type safety at the application layer and eliminate magic strings.
- **Action**: Create `AuthProvider(StrEnum)` with values `EMAIL`, `GOOGLE`, `APPLE`. Use in `map_provider`, `_ALLOWED_PROVIDERS`, and the User model.
- **Files**: `apps/api/src/coyo/models/user.py`, `apps/api/src/coyo/dependencies.py`

### 8. Review repository transaction boundary ownership
- **Priority**: Low
- **Category**: Architecture
- **Details**: `UserRepository.find_or_create_by_auth_uid` calls `commit()` directly. If called as part of a larger transaction, this prematurely commits the outer transaction's changes. Consider using `flush()` instead or having the caller own the commit.
- **Action**: Evaluate whether repositories should use `flush()` and let the request handler commit, or document the current pattern as intentional.
- **Files**: `apps/api/src/coyo/repositories/user.py`

---

## Features

### 9. Implement password reset
- **Priority**: Medium
- **Category**: Feature
- **Details**: "Forgot password?" text is rendered in `SignInFormScreen` as static text (no `onPress`, no `Pressable`). It looks like a link but is not interactive. Firebase provides `sendPasswordResetEmail` API.
- **Action**: Implement password reset flow or at minimum make the text non-styled (remove brand color) until implemented.
- **Files**: `apps/mobile/src/features/auth/SignInFormScreen.tsx`, `apps/mobile/src/services/firebase-auth.ts`

---

## Testing

### 10. Improve auth-related test coverage
- **Priority**: Medium
- **Category**: Testing
- **Details**: Several code paths lack unit tests:
  - `verify_firebase_token` function itself (expired, revoked, invalid token branches)
  - `IntegrityError` race condition retry path in `UserRepository.find_or_create_by_auth_uid`
  - Profile update path in `find_or_create_by_auth_uid` (when email/display_name/auth_provider differ)
- **Action**: Add unit tests for the above paths. Target 80%+ coverage for auth modules.
- **Files**: `apps/api/tests/unit/test_firebase_service.py` (new), `apps/api/tests/unit/test_repositories.py`

---

## Build / DevOps

### 11. Manage Firebase config files per environment via EAS Build
- **Priority**: High
- **Category**: Build / DevOps
- **Details**: `google-services.json` and `GoogleService-Info.plist` are currently gitignored and placed locally. This works for development but does not support environment separation (development vs production Firebase projects). Different Firebase projects should be used per environment for isolation.
- **Current state**: `app.config.ts` reads `googleServicesFile` / `GOOGLE_SERVICES_PLIST` from env vars with fallback to local files. The mechanism already supports environment switching.
- **Action**:
  1. Create a `firebase/` directory with per-environment subdirectories:
     ```
     apps/mobile/firebase/
       development/
         google-services.json
         GoogleService-Info.plist
       production/
         google-services.json
         GoogleService-Info.plist
     ```
  2. Development config files can be committed to the repo (no secrets).
  3. Production config files should be stored as **EAS Secrets** (Base64-encoded) and decoded at build time via a pre-install hook (`eas-build-pre-install.sh`).
  4. Update `app.config.ts` to select the correct path based on `APP_ENV`:
     ```ts
     googleServicesFile: process.env.APP_ENV === 'production'
       ? './firebase/production/google-services.json'
       : './firebase/development/google-services.json',
     ```
  5. Update `eas.json` preview/production profiles with the corresponding env vars (`GOOGLE_WEB_CLIENT_ID`, `GID_CLIENT_ID` per environment).
- **Files**: `apps/mobile/app.config.ts`, `apps/mobile/eas.json`, `apps/mobile/firebase/` (new), `apps/mobile/eas-build-pre-install.sh` (new)
