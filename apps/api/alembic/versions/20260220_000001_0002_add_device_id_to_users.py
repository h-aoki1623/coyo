"""Add device_id column to users table.

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-20 00:00:01+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "device_id",
            sa.String(36),
            nullable=False,
            comment="Client-generated UUID from X-Device-Id header",
        ),
    )
    op.create_unique_constraint("uq_users_device_id", "users", ["device_id"])
    op.create_index("ix_users_device_id", "users", ["device_id"])


def downgrade() -> None:
    op.drop_index("ix_users_device_id", table_name="users")
    op.drop_constraint("uq_users_device_id", "users", type_="unique")
    op.drop_column("users", "device_id")
