"""create normative documents table

Revision ID: 894e61ae7b32
Revises: 7c3e9a4b1d28
Create Date: 2026-08-27 21:07:20.858507

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "894e61ae7b32"
down_revision: str | Sequence[str] | None = "7c3e9a4b1d28"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "normative_documents",
        sa.Column(
            "source_type",
            sa.Enum(
                "federal_law",
                "ks_rf_ruling",
                "plenum_resolution",
                "expert_comment",
                name="normative_source_type",
            ),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("full_text", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("source_url", sa.String(length=1024), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column(
            "extra",
            sa.JSON().with_variant(
                postgresql.JSONB(astext_type=sa.Text()), "postgresql"
            ),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", "version", name="uq_normdoc_code_version"),
    )
    op.create_index(
        op.f("ix_normative_documents_code"),
        "normative_documents",
        ["code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_normative_documents_is_current"),
        "normative_documents",
        ["is_current"],
        unique=False,
    )
    op.create_index(
        op.f("ix_normative_documents_source_type"),
        "normative_documents",
        ["source_type"],
        unique=False,
    )
    op.create_index(
        "ix_normdoc_code_is_current",
        "normative_documents",
        ["code", "is_current"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_normdoc_code_is_current", table_name="normative_documents")
    op.drop_index(
        op.f("ix_normative_documents_source_type"), table_name="normative_documents"
    )
    op.drop_index(
        op.f("ix_normative_documents_is_current"), table_name="normative_documents"
    )
    op.drop_index(op.f("ix_normative_documents_code"), table_name="normative_documents")
    op.drop_table("normative_documents")
