"""Add memory tables for user profile and conversation summaries.

Creates:
- user_profile_attributes: structured profile facts (composite PK)
- user_profile_summaries: free-text user profile summary (1:1 with users)
- conversation_summaries: per-conversation summary with topic
- user_interests.summary, summary_updated_at, needs_summary_update columns
- conversations.memory_extracted flag

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-24 00:00:00+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -- user_profile_attributes table ----------------------------------------
    op.create_table(
        "user_profile_attributes",
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("key", sa.String(50), primary_key=True, nullable=False),
        sa.CheckConstraint(
            "key IN ('english_goal', 'job_industry', 'hometown_or_location', 'family_status')",
            name="ck_user_profile_attributes_key",
        ),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.8"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # -- user_profile_summaries table -----------------------------------------
    op.create_table(
        "user_profile_summaries",
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "conversation_count_at_update",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # -- conversation_summaries table -----------------------------------------
    op.create_table(
        "conversation_summaries",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "conversation_id",
            UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("topic_title", sa.Text(), nullable=False),
        sa.Column("source_keyword", sa.String(100), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_conversation_summaries_user_id_created_at",
        "conversation_summaries",
        ["user_id", sa.text("created_at DESC")],
    )

    # -- user_interests: add summary columns ----------------------------------
    op.add_column(
        "user_interests",
        sa.Column("summary", sa.String(200), nullable=True),
    )
    op.add_column(
        "user_interests",
        sa.Column(
            "summary_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "user_interests",
        sa.Column(
            "needs_summary_update",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )

    # -- conversations: add memory_extracted flag -----------------------------
    op.add_column(
        "conversations",
        sa.Column(
            "memory_extracted",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    # Backfill: if interests were already extracted, mark memory as extracted too
    op.execute(
        "UPDATE conversations SET memory_extracted = true WHERE interests_extracted = true"
    )


def downgrade() -> None:
    op.drop_column("conversations", "memory_extracted")
    op.drop_column("user_interests", "needs_summary_update")
    op.drop_column("user_interests", "summary_updated_at")
    op.drop_column("user_interests", "summary")
    op.drop_index(
        "ix_conversation_summaries_user_id_created_at",
        table_name="conversation_summaries",
    )
    op.drop_table("conversation_summaries")
    op.drop_table("user_profile_summaries")
    op.drop_table("user_profile_attributes")
