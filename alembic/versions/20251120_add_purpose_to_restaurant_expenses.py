"""add purpose to restaurant expenses

Revision ID: add_purpose_restaurant_expense
Revises: add_fields_restaurant_expense
Create Date: 2025-11-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_purpose_restaurant_expense"
down_revision: Union[str, Sequence[str], None] = "add_fields_restaurant_expense"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "restaurant_expenses",
        sa.Column("purpose", sa.String(), nullable=True),
    )
    op.execute(
        "UPDATE restaurant_expenses SET purpose = comment WHERE comment IS NOT NULL AND purpose IS NULL"
    )


def downgrade() -> None:
    op.drop_column("restaurant_expenses", "purpose")
