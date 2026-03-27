"""Rename keyword_type 'topic' to 'category' and add iab_category_id.

Renames the keyword_type value from 'topic' to 'category' in the
user_interests table to align with IAB Content Taxonomy terminology.
Also adds iab_category_id column for IAB category tracking.

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-27 00:00:00+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Drop old CHECK constraint first (must precede data update)
    op.drop_constraint("ck_user_interests_keyword_type", "user_interests")

    # 2. Update existing rows from 'topic' to 'category'
    op.execute(
        "UPDATE user_interests SET keyword_type = 'category' WHERE keyword_type = 'topic'"
    )

    # 3. Create new CHECK constraint with 'category' instead of 'topic'
    op.create_check_constraint(
        "ck_user_interests_keyword_type",
        "user_interests",
        "keyword_type IN ('category', 'entity')",
    )

    # 4. Add iab_category_id column
    op.add_column(
        "user_interests",
        sa.Column("iab_category_id", sa.String(10), nullable=True),
    )


def downgrade() -> None:
    # Remove iab_category_id column
    op.drop_column("user_interests", "iab_category_id")

    # Drop CHECK constraint first (must precede data update)
    op.drop_constraint("ck_user_interests_keyword_type", "user_interests")

    # Revert data
    op.execute(
        "UPDATE user_interests SET keyword_type = 'topic' WHERE keyword_type = 'category'"
    )

    # Recreate CHECK constraint with original values
    op.create_check_constraint(
        "ck_user_interests_keyword_type",
        "user_interests",
        "keyword_type IN ('topic', 'entity')",
    )
