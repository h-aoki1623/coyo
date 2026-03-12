#!/usr/bin/env python3
"""Create or reset the E2E test user in Firebase Authentication.

Usage:
    cd apps/api
    .venv/bin/python scripts/create_e2e_user.py

Requires:
    - FIREBASE_PROJECT_ID environment variable or .env file
    - Application Default Credentials (gcloud auth application-default login)

The script creates a user with email_verified=True so E2E tests
can sign in without going through the email verification flow.
"""

import os
import sys

# Ensure src/ is on the path so coyo.* imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import firebase_admin
from firebase_admin import auth, credentials

E2E_EMAIL = "e2e-test@coyo.to"
E2E_PASSWORD = "e2e-test-password-2026"
E2E_DISPLAY_NAME = "E2E Test User"


def main() -> None:
    # Load .env if present
    try:
        from dotenv import load_dotenv

        load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
    except ImportError:
        pass

    project_id = os.environ.get("FIREBASE_PROJECT_ID")
    if not project_id:
        print("ERROR: FIREBASE_PROJECT_ID environment variable is not set.")
        sys.exit(1)

    # Initialize Firebase Admin SDK with ADC
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred, {"projectId": project_id})

    # Check if user already exists
    try:
        user = auth.get_user_by_email(E2E_EMAIL)
        print(f"E2E user already exists: {user.uid}")

        # Ensure email is verified and password is current
        auth.update_user(
            user.uid,
            email_verified=True,
            password=E2E_PASSWORD,
            display_name=E2E_DISPLAY_NAME,
        )
        print("Updated: email_verified=True, password reset, display_name set.")

    except auth.UserNotFoundError:
        # Create new user
        user = auth.create_user(
            email=E2E_EMAIL,
            password=E2E_PASSWORD,
            display_name=E2E_DISPLAY_NAME,
            email_verified=True,
        )
        print(f"Created E2E user: {user.uid}")

    print(f"  Email: {E2E_EMAIL}")
    print(f"  Display Name: {E2E_DISPLAY_NAME}")
    print(f"  Email Verified: True")
    print("Done.")


if __name__ == "__main__":
    main()
