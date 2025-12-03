"""Add restaurant payment methods mapping.

Revision ID: bc1c99c5a64d
Revises: bb59f0f2d7a4
Create Date: 2025-10-24 20:12:10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "bc1c99c5a64d"
down_revision: Union[str, Sequence[str], None] = "bb59f0f2d7a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "restaurant_payment_methods",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("up_company_id", sa.Integer(), nullable=False),
        sa.Column("payment_method_id", sa.Integer(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["up_company_id"], ["up_company.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payment_method_id"], ["payment_methods.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("up_company_id", "payment_method_id", name="uq_restaurant_payment_methods_pair"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("restaurant_payment_methods")
