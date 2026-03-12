module.exports = {
  GoogleSignin: {
    configure: jest.fn(),
    hasPlayServices: jest.fn(() => Promise.resolve(true)),
    signIn: jest.fn(() =>
      Promise.resolve({ data: { idToken: 'mock-google-id-token' } }),
    ),
    signOut: jest.fn(() => Promise.resolve()),
  },
};
