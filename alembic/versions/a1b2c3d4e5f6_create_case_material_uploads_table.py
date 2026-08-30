"""create case material uploads table

Revision ID: a1b2c3d4e5f6
Revises: 6f8baca81cf7
Create Date: 2026-08-29

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "6f8baca81cf7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "case_material_uploads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "uploaded",
                "processing",
                "extracted",
                "text_extraction_failed",
                "failed",
                name="case_material_status",
            ),
            nullable=False,
        ),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column(
            "detected_documents",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "suggested_check_answers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_case_material_uploads_user_id"),
        "case_material_uploads",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_case_material_uploads_status"),
        "case_material_uploads",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_case_material_uploads_created_at"),
        "case_material_uploads",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_case_material_uploads_created_at"), table_name="case_material_uploads"
    )
    op.drop_index(
        op.f("ix_case_material_uploads_status"), table_name="case_material_uploads"
    )
    op.drop_index(
        op.f("ix_case_material_uploads_user_id"), table_name="case_material_uploads"
    )
    op.drop_table("case_material_uploads")
