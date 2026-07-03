"""one lead per email: normalize, dedupe, unique index

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Emails are stored lowercase from now on; normalize what's already there.
    op.execute("UPDATE leads SET email = LOWER(email)")
    # Dedupe, keeping each email's earliest submission (first-wins matches the new
    # idempotent create semantics). Orphaned resume files are left in object storage.
    op.execute(
        """
        DELETE FROM leads a
        WHERE EXISTS (
            SELECT 1 FROM leads b
            WHERE b.email = a.email
              AND (b.created_at < a.created_at
                   OR (b.created_at = a.created_at AND b.id < a.id))
        )
        """
    )
    op.drop_index(op.f("ix_leads_email"), table_name="leads")
    op.create_index(op.f("ix_leads_email"), "leads", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_leads_email"), table_name="leads")
    op.create_index(op.f("ix_leads_email"), "leads", ["email"])
