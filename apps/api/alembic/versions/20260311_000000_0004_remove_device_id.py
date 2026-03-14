"""Remove device_id column from users table.

Pre-release migration: deletes device-ID-only users (CASCADE cleans up
related records) and drops the device_id column entirely.

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-11 00:00:00+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Delete device-ID-only users (no Firebase UID).
    #    CASCADE on foreign keys will clean up related records.
    op.execute("DELETE FROM users WHERE firebase_uid IS NULL")

    # 2. Drop constraints that reference device_id or old auth_provider values
    op.drop_constraint("ck_users_has_identity", "users", type_="check")
    op.drop_constraint("ck_users_auth_provider_valid", "users", type_="check")

    # 3. Drop device_id index and unique constraint (created in migration 0002)
    op.drop_index("ix_users_device_id", table_name="users")
    op.drop_constraint("uq_users_device_id", "users", type_="unique")

    # 4. Drop device_id column
    op.drop_column("users", "device_id")

    # 5. Make firebase_uid NOT NULL (all remaining users have one)
    op.alter_column(
        "users",
        "firebase_uid",
        existing_type=sa.String(128),
        nullable=False,
    )

    # 6. Rename firebase_uid → auth_uid
    op.alter_column("users", "firebase_uid", new_column_name="auth_uid")

    # 7. Rename unique constraint uq_users_firebase_uid → uq_users_auth_uid
    op.drop_constraint("uq_users_firebase_uid", "users", type_="unique")
    op.create_unique_constraint("uq_users_auth_uid", "users", ["auth_uid"])

    # 8. Update auth_provider server_default from 'device_id' to 'email'
    op.alter_column(
        "users",
        "auth_provider",
        existing_type=sa.String(20),
        server_default="email",
    )

    # 9. Re-create auth_provider check constraint without 'device_id'
    op.create_check_constraint(
        "ck_users_auth_provider_valid",
        "users",
        "auth_provider IN ('email', 'google', 'apple')",
    )


def downgrade() -> None:
    # Reverse: drop new check constraint
    op.drop_constraint("ck_users_auth_provider_valid", "users", type_="check")

    # Restore auth_provider server_default to 'device_id'
    op.alter_column(
        "users",
        "auth_provider",
        existing_type=sa.String(20),
        server_default="device_id",
    )

    # Rename auth_uid → firebase_uid
    op.alter_column("users", "auth_uid", new_column_name="firebase_uid")

    # Rename unique constraint uq_users_auth_uid → uq_users_firebase_uid
    op.drop_constraint("uq_users_auth_uid", "users", type_="unique")
    op.create_unique_constraint("uq_users_firebase_uid", "users", ["firebase_uid"])

    # Make firebase_uid nullable again
    op.alter_column(
        "users",
        "firebase_uid",
        existing_type=sa.String(128),
        nullable=True,
    )

    # Re-add device_id column (nullable — data is gone)
    op.add_column(
        "users",
        sa.Column(
            "device_id",
            sa.String(36),
            nullable=True,
            comment="Client-generated UUID from X-Device-Id header",
        ),
    )

    # Re-create device_id unique constraint and index
    op.create_unique_constraint("uq_users_device_id", "users", ["device_id"])
    op.create_index("ix_users_device_id", "users", ["device_id"])

    # Restore original check constraints
    op.create_check_constraint(
        "ck_users_auth_provider_valid",
        "users",
        "auth_provider IN ('device_id', 'email', 'google', 'apple')",
    )
    op.create_check_constraint(
        "ck_users_has_identity",
        "users",
        "device_id IS NOT NULL OR firebase_uid IS NOT NULL",
    )
