module.exports = {
  appleAuth: {
    performRequest: jest.fn(() =>
      Promise.resolve({
        identityToken: 'mock-apple-identity-token',
        nonce: 'mock-nonce',
        fullName: { givenName: 'Test', familyName: 'User' },
      }),
    ),
    Operation: { LOGIN: 1 },
    Scope: { EMAIL: 0, FULL_NAME: 1 },
  },
};
