"""Add Firebase authentication columns to users table.

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-09 00:00:00+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add Firebase-related columns
    op.add_column(
        "users",
        sa.Column("firebase_uid", sa.String(128), nullable=True, comment="Firebase Authentication UID"),
    )
    op.add_column(
        "users",
        sa.Column("email", sa.String(255), nullable=True, comment="User email from Firebase"),
    )
    op.add_column(
        "users",
        sa.Column("display_name", sa.String(255), nullable=True, comment="Display name from Firebase"),
    )
    op.add_column(
        "users",
        sa.Column(
            "auth_provider",
            sa.String(20),
            nullable=False,
            server_default="device_id",
            comment="Authentication provider: device_id, email, google, apple",
        ),
    )

    # Make device_id nullable (Firebase users may not have one)
    op.alter_column("users", "device_id", existing_type=sa.String(36), nullable=True)

    # Add indexes and constraints
    op.create_unique_constraint("uq_users_firebase_uid", "users", ["firebase_uid"])
    op.create_index("ix_users_email", "users", ["email"])
    op.create_check_constraint(
        "ck_users_has_identity",
        "users",
        "device_id IS NOT NULL OR firebase_uid IS NOT NULL",
    )
    op.create_check_constraint(
        "ck_users_auth_provider_valid",
        "users",
        "auth_provider IN ('device_id', 'email', 'google', 'apple')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_auth_provider_valid", "users", type_="check")
    op.drop_constraint("ck_users_has_identity", "users", type_="check")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_constraint("uq_users_firebase_uid", "users", type_="unique")

    op.drop_column("users", "auth_provider")
    op.drop_column("users", "display_name")
    op.drop_column("users", "email")
    op.drop_column("users", "firebase_uid")

    # Restore device_id to NOT NULL
    op.alter_column("users", "device_id", existing_type=sa.String(36), nullable=False)
