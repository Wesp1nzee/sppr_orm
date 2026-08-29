"""add search vector to normative documents

Revision ID: 6f8baca81cf7
Revises: f4e0b1dba569
Create Date: 2026-08-29 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "6f8baca81cf7"
down_revision: str | Sequence[str] | None = "f4e0b1dba569"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "normative_documents",
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE normative_documents SET search_vector = "
            "to_tsvector('russian', title || ' ' || full_text || ' ' "
            "|| coalesce(summary, ''))"
        )
    )
    op.create_index(
        "ix_normdoc_search_vector",
        "normative_documents",
        ["search_vector"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_normdoc_search_vector", table_name="normative_documents")
    op.drop_column("normative_documents", "search_vector")
