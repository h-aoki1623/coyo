"""Remove topic column from conversations table.

Topic is no longer persisted in the database. Users still select a topic
on the home screen, but it flows client-side only and is passed via
FormData on each turn submission for the LLM system prompt.

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-17 00:00:00+00:00

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("conversations", "topic")


def downgrade() -> None:
    raise NotImplementedError(
        "One-way migration: topic data was intentionally discarded. "
        "Re-add the column manually with a default value if rollback is needed."
    )
