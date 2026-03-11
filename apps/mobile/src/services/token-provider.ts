/**
 * Token provider — breaks the require cycle between api/client and stores/auth-store.
 *
 * Both api/client.ts and api/sse-client.ts need to read the current Firebase
 * token, while auth-store.ts needs to call apiClient. Importing auth-store
 * directly from the API layer creates a circular dependency.
 *
 * This module holds a lazily-set token getter that auth-store registers at
 * initialisation time, so the API layer never imports auth-store.
 */

type TokenGetter = () => Promise<string | null>;

let _getToken: TokenGetter = async () => null;

/**
 * Register the token getter. Called once by auth-store during store creation.
 */
export function registerTokenGetter(getter: TokenGetter): void {
  _getToken = getter;
}

/**
 * Retrieve the current Firebase ID token (or null if not authenticated).
 * Safe to call from api/client.ts without creating a circular import.
 */
export function getAuthToken(): Promise<string | null> {
  return _getToken();
}
