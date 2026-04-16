import { linking } from './linking';

describe('linking config', () => {
  it('maps password-reset-done to PasswordResetSuccess', () => {
    expect(linking.config?.screens).toEqual({
      PasswordResetSuccess: 'password-reset-done',
    });
  });

  it('has coyo:// prefix', () => {
    expect(linking.prefixes).toEqual(['coyo://']);
  });
});
