/**
 * Type declarations for native Firebase modules.
 *
 * These packages provide their own types when installed via npm,
 * but are declared here for TypeScript compilation in environments
 * where the native packages are not yet installed (e.g., CI, worktrees).
 */

declare module '@react-native-firebase/auth' {
  export namespace FirebaseAuthTypes {
    interface UserInfo {
      providerId: string
      uid: string
      displayName: string | null
      email: string | null
      phoneNumber: string | null
      photoURL: string | null
    }

    interface User {
      uid: string
      email: string | null
      displayName: string | null
      emailVerified: boolean
      providerData: UserInfo[]
      getIdToken(forceRefresh?: boolean): Promise<string>
      reload(): Promise<void>
      sendEmailVerification(): Promise<void>
      updateProfile(profile: { displayName?: string | null; photoURL?: string | null }): Promise<void>
    }

    interface UserCredential {
      user: User
    }
  }

  interface AuthCredential {
    providerId: string
    token: string
    secret?: string
  }

  interface Auth {
    currentUser: FirebaseAuthTypes.User | null
    signInWithEmailAndPassword(email: string, password: string): Promise<FirebaseAuthTypes.UserCredential>
    createUserWithEmailAndPassword(email: string, password: string): Promise<FirebaseAuthTypes.UserCredential>
    signInWithCredential(credential: AuthCredential): Promise<FirebaseAuthTypes.UserCredential>
    signOut(): Promise<void>
    onAuthStateChanged(callback: (user: FirebaseAuthTypes.User | null) => void): () => void
  }

  const auth: {
    (): Auth
    GoogleAuthProvider: { credential(idToken: string | null, accessToken?: string | null): AuthCredential }
    AppleAuthProvider: { credential(identityToken: string, nonce: string): AuthCredential }
  }

  export { FirebaseAuthTypes }
  export default auth
}

declare module '@react-native-google-signin/google-signin' {
  export const GoogleSignin: {
    configure(options: { webClientId?: string; offlineAccess?: boolean }): void
    hasPlayServices(options?: { showPlayServicesUpdateDialog?: boolean }): Promise<boolean>
    signIn(): Promise<{ data: { idToken: string | null } | null }>
    signOut(): Promise<void>
  }
}

declare module '@invertase/react-native-apple-authentication' {
  export const appleAuth: {
    performRequest(options: {
      requestedOperation: number
      requestedScopes: number[]
    }): Promise<{
      identityToken: string | null
      nonce: string
      fullName: { givenName: string | null; familyName: string | null } | null
    }>
    Operation: { LOGIN: number }
    Scope: { EMAIL: number; FULL_NAME: number }
  }
}
