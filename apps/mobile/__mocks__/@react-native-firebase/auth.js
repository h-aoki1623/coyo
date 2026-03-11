const mockAuth = jest.fn(() => ({
  signInWithEmailAndPassword: jest.fn(),
  createUserWithEmailAndPassword: jest.fn(),
  signInWithCredential: jest.fn(),
  signOut: jest.fn(),
  onAuthStateChanged: jest.fn(() => jest.fn()),
  currentUser: null,
}));
mockAuth.GoogleAuthProvider = { credential: jest.fn() };
mockAuth.AppleAuthProvider = { credential: jest.fn() };

module.exports = mockAuth;
module.exports.default = mockAuth;
