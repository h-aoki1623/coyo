"""Add pgvector embedding columns and conversation memory snapshot.

Adds:
- pgvector extension (Supabase has this preinstalled).
- user_interests.embedding vector(1536) NULL with STORAGE EXTERNAL.
- conversation_summaries.embedding vector(1536) NULL with STORAGE EXTERNAL.
- conversations.memory_context_text TEXT NULL (snapshot of injected memory).
- conversations.memory_context_built_at TIMESTAMPTZ NULL.

NOTE: We deliberately do NOT create HNSW/ivfflat indexes — the candidate
set per user is small (<=200 rows) and ANN indexes hurt accuracy at this
cardinality. Existing PK / user_id indexes already cover the queries.

Revision ID: 0010
Revises: 0009
Create Date: 2026-04-08 00:00:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _is_postgres() -> bool:
    """Return True when the migration is running against PostgreSQL."""
    bind = op.get_bind()
    return bind.dialect.name == "postgresql"


def upgrade() -> None:
    postgres = _is_postgres()

    if postgres:
        # Supabase has pgvector preinstalled. CREATE EXTENSION IF NOT EXISTS
        # is idempotent and a no-op when the extension is already enabled.
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Choose the column type per dialect: pgvector on Postgres, opaque
    # binary blob on others (sqlite test envs ignore the column).
    embedding_type: sa.types.TypeEngine[object]
    if postgres:
        from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]

        embedding_type = Vector(1536)
    else:
        embedding_type = sa.LargeBinary()  # type: ignore[assignment]

    op.add_column(
        "user_interests",
        sa.Column("embedding", embedding_type, nullable=True),
    )
    op.add_column(
        "conversation_summaries",
        sa.Column("embedding", embedding_type, nullable=True),
    )
    op.add_column(
        "conversations",
        sa.Column("memory_context_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "conversations",
        sa.Column(
            "memory_context_built_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    if postgres:
        # Disable inline pglz compression for the embedding columns.
        # vector(1536) is ~6KB of float data with no useful redundancy, so
        # forcing STORAGE EXTERNAL keeps reads cheap (no decompression).
        op.execute("ALTER TABLE user_interests ALTER COLUMN embedding SET STORAGE EXTERNAL")
        op.execute(
            "ALTER TABLE conversation_summaries ALTER COLUMN embedding SET STORAGE EXTERNAL"
        )


def downgrade() -> None:
    op.drop_column("conversations", "memory_context_built_at")
    op.drop_column("conversations", "memory_context_text")
    op.drop_column("conversation_summaries", "embedding")
    op.drop_column("user_interests", "embedding")
    # Intentionally do NOT drop the vector extension — other migrations
    # or features may rely on it. Removing the extension is a manual op.
