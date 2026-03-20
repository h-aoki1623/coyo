"""Add user_interests table and supporting columns.

Creates:
- user_interests: stores extracted interest keywords with 2-layer weight model
- users.conversation_count: tracks total completed conversations for gap calculation
- conversations.interests_extracted: idempotency flag for extraction

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-20 00:00:00+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -- user_interests table -------------------------------------------------
    op.create_table(
        "user_interests",
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("keyword", sa.String(100), primary_key=True),
        sa.Column(
            "keyword_type",
            sa.String(10),
            nullable=False,
        ),
        sa.CheckConstraint(
            "keyword_type IN ('topic', 'entity')",
            name="ck_user_interests_keyword_type",
        ),
        sa.Column("is_news_relevant", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("total_mentions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("short_term_stored", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("last_mentioned_conv_idx", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # Note: no separate user_id index needed — composite PK (user_id, keyword)
    # already covers user_id-only queries via leftmost prefix rule.

    # -- users.conversation_count ---------------------------------------------
    op.add_column(
        "users",
        sa.Column(
            "conversation_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    # -- conversations.interests_extracted ------------------------------------
    op.add_column(
        "conversations",
        sa.Column(
            "interests_extracted",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("conversations", "interests_extracted")
    op.drop_column("users", "conversation_count")
    op.drop_table("user_interests")
