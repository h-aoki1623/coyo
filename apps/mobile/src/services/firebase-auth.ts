/**
 * Firebase Authentication service.
 *
 * Wraps @react-native-firebase/auth methods for sign-in,
 * sign-up, SSO, and token management.
 */

import auth, { FirebaseAuthTypes } from '@react-native-firebase/auth';
import { GoogleSignin } from '@react-native-google-signin/google-signin';
import { appleAuth } from '@invertase/react-native-apple-authentication';
import Constants from 'expo-constants';

// Configure Google Sign-In with web client ID from app config
const googleWebClientId = Constants.expoConfig?.extra?.googleWebClientId ?? '';

// Build the continueUrl for email verification redirect.
// After Firebase verifies the email in the browser, it redirects here,
// which opens the app via the coyo:// URL scheme.
const API_BASE_URL = Constants.expoConfig?.extra?.apiBaseUrl ?? 'http://localhost:8000';
const EMAIL_VERIFICATION_CONTINUE_URL = `${API_BASE_URL}/api/auth/app-redirect`;

// ActionCodeSettings for email verification links.
// Configured to redirect users back to the app after email verification.
const BUNDLE_ID = Constants.expoConfig?.ios?.bundleIdentifier ?? 'to.coyo.app';
const PACKAGE_NAME = Constants.expoConfig?.android?.package ?? 'to.coyo.app';

const EMAIL_VERIFICATION_SETTINGS = {
  url: EMAIL_VERIFICATION_CONTINUE_URL,
  handleCodeInApp: false,
  iOS: { bundleId: BUNDLE_ID },
  android: { packageName: PACKAGE_NAME, installApp: false },
};

/**
 * Wrapper for User.sendEmailVerification that works around a type definition
 * mismatch in @react-native-firebase/auth v21 where the method-style API's
 * optional ActionCodeSettings parameter is not recognized by TypeScript.
 * The runtime API correctly accepts the parameter.
 */
async function sendVerificationEmail(user: FirebaseAuthTypes.User): Promise<void> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  await (user as any).sendEmailVerification(EMAIL_VERIFICATION_SETTINGS);
}

export function configureGoogleSignIn(): void {
  if (googleWebClientId) {
    GoogleSignin.configure({ webClientId: googleWebClientId });
  }
}

export async function signUpWithEmail(
  email: string,
  password: string,
  displayName: string,
): Promise<FirebaseAuthTypes.UserCredential> {
  const credential = await auth().createUserWithEmailAndPassword(email, password);
  if (credential.user) {
    await credential.user.updateProfile({ displayName });
    // Force-refresh the ID token so the "name" claim reflects the new displayName.
    // Without this, the first token sent to the backend would lack the name.
    await credential.user.getIdToken(true);
    await sendVerificationEmail(credential.user);
  }
  return credential;
}

export async function signInWithEmail(
  email: string,
  password: string,
): Promise<FirebaseAuthTypes.UserCredential> {
  return auth().signInWithEmailAndPassword(email, password);
}

export async function signInWithGoogle(): Promise<FirebaseAuthTypes.UserCredential> {
  await GoogleSignin.hasPlayServices({ showPlayServicesUpdateDialog: true });
  const response = await GoogleSignin.signIn();

  if (!response.data?.idToken) {
    throw new Error('Google Sign-In failed: no ID token');
  }

  const googleCredential = auth.GoogleAuthProvider.credential(response.data.idToken);
  return auth().signInWithCredential(googleCredential);
}

export async function signInWithApple(): Promise<FirebaseAuthTypes.UserCredential> {
  const appleAuthResponse = await appleAuth.performRequest({
    requestedOperation: appleAuth.Operation.LOGIN,
    requestedScopes: [appleAuth.Scope.EMAIL, appleAuth.Scope.FULL_NAME],
  });

  if (!appleAuthResponse.identityToken) {
    throw new Error('Apple Sign-In failed: no identity token');
  }

  const { identityToken, nonce } = appleAuthResponse;
  const appleCredential = auth.AppleAuthProvider.credential(identityToken, nonce);
  const credential = await auth().signInWithCredential(appleCredential);

  // Apple only provides the name on the first sign-in
  if (appleAuthResponse.fullName?.givenName && credential.user) {
    const fullName = [
      appleAuthResponse.fullName.givenName,
      appleAuthResponse.fullName.familyName,
    ]
      .filter(Boolean)
      .join(' ');
    if (fullName) {
      await credential.user.updateProfile({ displayName: fullName });
    }
  }

  return credential;
}

export async function signOut(): Promise<void> {
  await auth().signOut();
}

export async function getIdToken(): Promise<string | null> {
  const user = auth().currentUser;
  if (!user) return null;
  return user.getIdToken();
}

export function onAuthStateChanged(
  callback: (user: FirebaseAuthTypes.User | null) => void,
): () => void {
  return auth().onAuthStateChanged(callback);
}

export async function sendEmailVerification(): Promise<void> {
  const user = auth().currentUser;
  if (!user) throw new Error('No authenticated user');
  await sendVerificationEmail(user);
}

export async function reloadUser(): Promise<FirebaseAuthTypes.User | null> {
  const user = auth().currentUser;
  if (!user) return null;
  await user.reload();
  return auth().currentUser;
}
