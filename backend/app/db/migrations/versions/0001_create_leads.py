"""create leads table

Revision ID: 0001
Revises:
Create Date: 2026-07-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "leads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("first_name", sa.String(length=255), nullable=False),
        sa.Column("last_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("resume_path", sa.String(length=512), nullable=False),
        sa.Column("resume_filename", sa.String(length=255), nullable=False),
        sa.Column("resume_content_type", sa.String(length=255), nullable=False),
        sa.Column(
            "state",
            sa.Enum("PENDING", "REACHED_OUT", name="lead_state"),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("reached_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_leads_created_at"), "leads", ["created_at"])
    op.create_index(op.f("ix_leads_email"), "leads", ["email"])


def downgrade() -> None:
    op.drop_index(op.f("ix_leads_email"), table_name="leads")
    op.drop_index(op.f("ix_leads_created_at"), table_name="leads")
    op.drop_table("leads")
    sa.Enum(name="lead_state").drop(op.get_bind(), checkfirst=True)
