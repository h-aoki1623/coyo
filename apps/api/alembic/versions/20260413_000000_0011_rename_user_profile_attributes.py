"""Rename user_profile_attributes table to user_attributes.

Renames:
- Table: user_profile_attributes → user_attributes
- PK index: user_profile_attributes_pkey → user_attributes_pkey
- Check constraint: ck_user_profile_attributes_key → ck_user_attributes_key
- FK constraint: user_profile_attributes_user_id_fkey → user_attributes_user_id_fkey

All operations are metadata-only (no data movement).

Revision ID: 0011
Revises: 0010
Create Date: 2026-04-13 00:00:00+00:00
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.rename_table("user_profile_attributes", "user_attributes")
    op.execute("ALTER INDEX user_profile_attributes_pkey RENAME TO user_attributes_pkey")
    op.execute(
        "ALTER TABLE user_attributes RENAME CONSTRAINT "
        "ck_user_profile_attributes_key TO ck_user_attributes_key"
    )
    op.execute(
        "ALTER TABLE user_attributes RENAME CONSTRAINT "
        "user_profile_attributes_user_id_fkey TO user_attributes_user_id_fkey"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE user_attributes RENAME CONSTRAINT "
        "user_attributes_user_id_fkey TO user_profile_attributes_user_id_fkey"
    )
    op.execute(
        "ALTER TABLE user_attributes RENAME CONSTRAINT "
        "ck_user_attributes_key TO ck_user_profile_attributes_key"
    )
    op.execute("ALTER INDEX user_attributes_pkey RENAME TO user_profile_attributes_pkey")
    op.rename_table("user_attributes", "user_profile_attributes")
