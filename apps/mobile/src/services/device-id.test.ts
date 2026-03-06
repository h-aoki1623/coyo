import * as SecureStore from 'expo-secure-store';
import * as Crypto from 'expo-crypto';
import { getOrCreateDeviceId } from './device-id';

const mockGetItemAsync = SecureStore.getItemAsync as jest.MockedFunction<
  typeof SecureStore.getItemAsync
>;
const mockSetItemAsync = SecureStore.setItemAsync as jest.MockedFunction<
  typeof SecureStore.setItemAsync
>;
const mockRandomUUID = Crypto.randomUUID as jest.MockedFunction<
  typeof Crypto.randomUUID
>;

describe('getOrCreateDeviceId', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('returns existing device ID from SecureStore when present', async () => {
    mockGetItemAsync.mockResolvedValue('existing-device-id-abc');

    const result = await getOrCreateDeviceId();

    expect(result).toBe('existing-device-id-abc');
    expect(mockGetItemAsync).toHaveBeenCalledWith('coyo_device_id', {
      keychainAccessible: SecureStore.AFTER_FIRST_UNLOCK,
    });
    expect(mockRandomUUID).not.toHaveBeenCalled();
    expect(mockSetItemAsync).not.toHaveBeenCalled();
  });

  it('generates a new UUID and saves it when no existing ID', async () => {
    mockGetItemAsync.mockResolvedValue(null);
    mockRandomUUID.mockReturnValue('new-uuid-5678');

    const result = await getOrCreateDeviceId();

    expect(result).toBe('new-uuid-5678');
    expect(mockRandomUUID).toHaveBeenCalledTimes(1);
    expect(mockSetItemAsync).toHaveBeenCalledWith(
      'coyo_device_id',
      'new-uuid-5678',
      { keychainAccessible: SecureStore.AFTER_FIRST_UNLOCK },
    );
  });

  it('uses AFTER_FIRST_UNLOCK accessibility for keychain access', async () => {
    mockGetItemAsync.mockResolvedValue(null);
    mockRandomUUID.mockReturnValue('test-uuid');

    await getOrCreateDeviceId();

    expect(mockGetItemAsync).toHaveBeenCalledWith(
      'coyo_device_id',
      expect.objectContaining({
        keychainAccessible: SecureStore.AFTER_FIRST_UNLOCK,
      }),
    );
    expect(mockSetItemAsync).toHaveBeenCalledWith(
      'coyo_device_id',
      'test-uuid',
      expect.objectContaining({
        keychainAccessible: SecureStore.AFTER_FIRST_UNLOCK,
      }),
    );
  });

  it('returns a new ID each time if SecureStore always returns null', async () => {
    mockGetItemAsync.mockResolvedValue(null);
    mockRandomUUID
      .mockReturnValueOnce('uuid-call-1')
      .mockReturnValueOnce('uuid-call-2');

    const result1 = await getOrCreateDeviceId();
    const result2 = await getOrCreateDeviceId();

    expect(result1).toBe('uuid-call-1');
    expect(result2).toBe('uuid-call-2');
    expect(mockSetItemAsync).toHaveBeenCalledTimes(2);
  });
});
