"""create audit log entries table

Revision ID: f4e0b1dba569
Revises: 6e8244721d70
Create Date: 2026-08-28 20:21:15.251252

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f4e0b1dba569"
down_revision: str | Sequence[str] | None = "6e8244721d70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "audit_log_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("user_role", sa.String(length=32), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_audit_log_entries_event_type"),
        "audit_log_entries",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_log_entries_user_id"),
        "audit_log_entries",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_log_entries_created_at"),
        "audit_log_entries",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_audit_log_entries_created_at"), table_name="audit_log_entries"
    )
    op.drop_index(op.f("ix_audit_log_entries_user_id"), table_name="audit_log_entries")
    op.drop_index(
        op.f("ix_audit_log_entries_event_type"), table_name="audit_log_entries"
    )
    op.drop_table("audit_log_entries")
