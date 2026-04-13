"""Add topic column to conversations table.

Stores the topic key selected by the user (sports, business, etc.)
so memory extraction can resolve the topic keyword for interest upsert.

Revision ID: 0012
Revises: 0011
Create Date: 2026-04-13 00:00:01+00:00
"""

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column(
            "topic",
            sa.String(20),
            nullable=True,
            comment="Topic key selected by user (sports, business, etc. or 'suggested')",
        ),
    )


def downgrade() -> None:
    op.drop_column("conversations", "topic")
