"""create generated documents table

Revision ID: 6e8244721d70
Revises: 894e61ae7b32
Create Date: 2026-08-27 23:30:22.164242

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "6e8244721d70"
down_revision: str | Sequence[str] | None = "894e61ae7b32"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "generated_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("check_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "document_type",
            sa.Enum(
                "exclusion_motion",
                "court_decision_copy_request",
                "data_request_complaint",
                "officer_checklist",
                "legalization_plan",
                name="document_type",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("draft", "finalized", name="document_status"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column(
            "content",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("template_version", sa.String(length=32), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["check_id"], ["checks.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_generated_documents_check_id"),
        "generated_documents",
        ["check_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_generated_documents_user_id"),
        "generated_documents",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_generated_documents_document_type"),
        "generated_documents",
        ["document_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_generated_documents_status"),
        "generated_documents",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_generated_documents_created_at"),
        "generated_documents",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_generated_documents_created_at"), table_name="generated_documents"
    )
    op.drop_index(
        op.f("ix_generated_documents_status"), table_name="generated_documents"
    )
    op.drop_index(
        op.f("ix_generated_documents_document_type"), table_name="generated_documents"
    )
    op.drop_index(
        op.f("ix_generated_documents_user_id"), table_name="generated_documents"
    )
    op.drop_index(
        op.f("ix_generated_documents_check_id"), table_name="generated_documents"
    )
    op.drop_table("generated_documents")
