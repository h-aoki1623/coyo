import { validatePassword, isEmailValid, MIN_PASSWORD_LENGTH } from './validation';

describe('validation', () => {
  describe('validatePassword', () => {
    it('returns an error for passwords shorter than MIN_PASSWORD_LENGTH', () => {
      expect(validatePassword('short')).not.toBeNull();
      expect(validatePassword('1234567')).not.toBeNull();
    });

    it('returns null at exactly MIN_PASSWORD_LENGTH', () => {
      expect(MIN_PASSWORD_LENGTH).toBe(8);
      expect(validatePassword('12345678')).toBeNull();
    });

    it('returns null for passwords longer than MIN_PASSWORD_LENGTH', () => {
      expect(validatePassword('abcdefghij')).toBeNull();
    });

    it('returns an error for an empty password', () => {
      expect(validatePassword('')).not.toBeNull();
    });

    it('counts unicode characters by length (JS string length) and accepts >= 8 code units', () => {
      // "パスワード12345" is 10 code units — valid.
      expect(validatePassword('パスワード12345')).toBeNull();
      // 3 kanji characters = 3 code units, below min.
      expect(validatePassword('日本語')).not.toBeNull();
    });
  });

  describe('isEmailValid', () => {
    it('accepts a standard email address', () => {
      expect(isEmailValid('user@example.com')).toBe(true);
    });

    it('rejects strings missing the @ character', () => {
      expect(isEmailValid('userexample.com')).toBe(false);
    });

    it('rejects strings missing the domain portion', () => {
      expect(isEmailValid('user@')).toBe(false);
      expect(isEmailValid('user@domain')).toBe(false); // no TLD dot
    });

    it('rejects empty strings', () => {
      expect(isEmailValid('')).toBe(false);
    });

    it('trims leading/trailing whitespace before validating', () => {
      expect(isEmailValid('  user@example.com  ')).toBe(true);
      expect(isEmailValid('   ')).toBe(false);
    });

    it('rejects embedded whitespace in the local or domain portion', () => {
      expect(isEmailValid('us er@example.com')).toBe(false);
      expect(isEmailValid('user@exa mple.com')).toBe(false);
    });
  });
});
