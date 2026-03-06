import * as SecureStore from 'expo-secure-store';
import * as Crypto from 'expo-crypto';

const DEVICE_ID_KEY = 'coyo_device_id';

/**
 * Retrieve or generate a persistent device identifier.
 * Stored in Keychain (iOS) / Keystore (Android) via expo-secure-store
 * with AFTER_FIRST_UNLOCK accessibility for background access.
 */
export async function getOrCreateDeviceId(): Promise<string> {
  // Attempt to retrieve existing ID from secure storage
  const existing = await SecureStore.getItemAsync(DEVICE_ID_KEY, {
    keychainAccessible: SecureStore.AFTER_FIRST_UNLOCK,
  });
  if (existing) return existing;

  // Generate new UUID v4
  const newId = Crypto.randomUUID();

  // Persist to Keychain/Keystore
  await SecureStore.setItemAsync(DEVICE_ID_KEY, newId, {
    keychainAccessible: SecureStore.AFTER_FIRST_UNLOCK,
  });

  return newId;
}
