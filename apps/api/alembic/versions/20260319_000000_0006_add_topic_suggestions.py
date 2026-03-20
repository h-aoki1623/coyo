"""Add topic suggestions tables and link to conversations.

Creates:
- topic_suggestions: stores generated trending topic suggestions
- user_topic_suggestions: links users to their assigned suggestions
- conversations.topic_suggestion_id: FK to topic_suggestions

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-19 00:00:00+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -- topic_suggestions table -------------------------------------------
    op.create_table(
        "topic_suggestions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("source_keyword", sa.Text(), nullable=False),
        sa.Column("article_content", sa.Text(), nullable=False),
        sa.Column("article_url", sa.Text(), nullable=True),
        sa.Column("pool_type", sa.String(20), nullable=False, server_default="common"),
        sa.CheckConstraint("pool_type IN ('common', 'personal')", name="ck_topic_pool_type"),
        sa.Column("generated_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_topic_suggestions_date_pool",
        "topic_suggestions",
        ["generated_date", "pool_type"],
    )

    # -- user_topic_suggestions table --------------------------------------
    op.create_table(
        "user_topic_suggestions",
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "topic_suggestion_id",
            UUID(as_uuid=True),
            sa.ForeignKey("topic_suggestions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("relevance_score", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_user_topic_suggestions_user_created",
        "user_topic_suggestions",
        ["user_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_user_topic_suggestions_suggestion_id",
        "user_topic_suggestions",
        ["topic_suggestion_id"],
    )

    # -- conversations.topic_suggestion_id ---------------------------------
    op.add_column(
        "conversations",
        sa.Column(
            "topic_suggestion_id",
            UUID(as_uuid=True),
            sa.ForeignKey("topic_suggestions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_conversations_topic_suggestion_id",
        "conversations",
        ["topic_suggestion_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_conversations_topic_suggestion_id", table_name="conversations")
    op.drop_column("conversations", "topic_suggestion_id")
    op.drop_index("ix_user_topic_suggestions_suggestion_id", table_name="user_topic_suggestions")
    op.drop_index("ix_user_topic_suggestions_user_created", table_name="user_topic_suggestions")
    op.drop_table("user_topic_suggestions")
    op.drop_index("ix_topic_suggestions_date_pool", table_name="topic_suggestions")
    op.drop_table("topic_suggestions")
