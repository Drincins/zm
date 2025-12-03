"""add status to payment_links

Revision ID: add_status_payment_links
Revises: add_payment_links
Create Date: 2025-11-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_status_payment_links"
down_revision: Union[str, Sequence[str], None] = "add_payment_links"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "payment_links",
        sa.Column("status", sa.String(length=32), nullable=False, server_default="received"),
    )
    # drop default if any
    op.alter_column("payment_links", "status", server_default=None)


def downgrade() -> None:
    op.drop_column("payment_links", "status")
