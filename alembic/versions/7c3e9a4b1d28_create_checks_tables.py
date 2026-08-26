"""create checks tables

Revision ID: 7c3e9a4b1d28
Revises: dc9c85a65f26
Create Date: 2026-08-26

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "7c3e9a4b1d28"
down_revision: str | Sequence[str] | None = "dc9c85a65f26"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "checks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "role_at_run",
            sa.Enum(
                "lawyer",
                "investigator",
                "officer",
                "admin",
                name="user_role",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("case_title", sa.String(length=255), nullable=True),
        sa.Column(
            "input_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("rules_version", sa.String(length=32), nullable=False),
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
    op.create_index(op.f("ix_checks_user_id"), "checks", ["user_id"], unique=False)
    op.create_index(op.f("ix_checks_status"), "checks", ["status"], unique=False)
    op.create_index(
        op.f("ix_checks_created_at"), "checks", ["created_at"], unique=False
    )

    op.create_table(
        "criterion_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("check_id", sa.Uuid(), nullable=False),
        sa.Column("criterion_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column(
            "legal_references",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "recommendations",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("priority_for_role", sa.Boolean(), nullable=False),
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
        sa.ForeignKeyConstraint(["check_id"], ["checks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "check_id",
            "criterion_number",
            name="uq_criterion_results_check_criterion",
        ),
    )
    op.create_index(
        op.f("ix_criterion_results_check_id"),
        "criterion_results",
        ["check_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_criterion_results_check_id"), table_name="criterion_results")
    op.drop_table("criterion_results")
    op.drop_index(op.f("ix_checks_created_at"), table_name="checks")
    op.drop_index(op.f("ix_checks_status"), table_name="checks")
    op.drop_index(op.f("ix_checks_user_id"), table_name="checks")
    op.drop_table("checks")
