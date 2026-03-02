"""Initial schema: users, user_settings, conversations, turns, turn_corrections, correction_items.

Revision ID: 0001
Revises:
Create Date: 2026-02-20 00:00:00+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- user_settings ---
    op.create_table(
        "user_settings",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("ui_language", sa.String(5), nullable=False, server_default="ja"),
        sa.Column("correction_language", sa.String(5), nullable=False, server_default="ja"),
        sa.Column("time_limit_seconds", sa.Integer, nullable=False, server_default="1800"),
        sa.Column("tts_voice", sa.String(50), nullable=True),
        sa.Column("tts_speed", sa.Float, nullable=False, server_default="1.0"),
    )

    # --- conversations ---
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("topic", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("duration_seconds", sa.Integer, nullable=True),
        sa.Column("time_limit_seconds", sa.Integer, nullable=False, server_default="1800"),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_corrections", sa.Integer, nullable=False, server_default="0"),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- turns ---
    op.create_table(
        "turns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("audio_url", sa.String(500), nullable=True),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("correction_status", sa.String(20), nullable=False, server_default="none"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- turn_corrections ---
    op.create_table(
        "turn_corrections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "turn_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("turns.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("corrected_text", sa.Text, nullable=False),
        sa.Column("explanation", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- correction_items ---
    op.create_table(
        "correction_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "turn_correction_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("turn_corrections.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("original", sa.Text, nullable=False),
        sa.Column("corrected", sa.Text, nullable=False),
        sa.Column("original_sentence", sa.Text, nullable=False),
        sa.Column("corrected_sentence", sa.Text, nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("explanation", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("correction_items")
    op.drop_table("turn_corrections")
    op.drop_table("turns")
    op.drop_table("conversations")
    op.drop_table("user_settings")
    op.drop_table("users")
