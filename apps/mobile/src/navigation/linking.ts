/**
 * Deep linking configuration for React Navigation.
 *
 * Maps coyo:// URLs to in-app routes. Currently used for the post-reset
 * redirect: after the user resets their password on Firebase's hosted page,
 * the browser is redirected to coyo://password-reset-done, which opens the
 * app on the PasswordResetSuccess screen.
 */

import type { LinkingOptions } from '@react-navigation/native';

import type { AuthStackParamList } from './types';

export const linking: LinkingOptions<AuthStackParamList> = {
  prefixes: ['coyo://'],
  config: {
    screens: {
      PasswordResetSuccess: 'password-reset-done',
    },
  },
};
