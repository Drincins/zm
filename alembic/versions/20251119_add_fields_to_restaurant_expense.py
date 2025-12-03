"""add operation_type and transferred_to_statement to restaurant_expenses

Revision ID: add_fields_restaurant_expense
Revises: add_is_primary_company
Create Date: 2025-11-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_fields_restaurant_expense"
down_revision: Union[str, Sequence[str], None] = "add_is_primary_company"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "restaurant_expenses",
        sa.Column("operation_type", sa.String(length=20), nullable=False, server_default="списание"),
    )
    op.add_column(
        "restaurant_expenses",
        sa.Column("transferred_to_statement", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index(
        "ix_rest_expenses_transferred",
        "restaurant_expenses",
        ["transferred_to_statement"],
        unique=False,
    )
    op.alter_column("restaurant_expenses", "operation_type", server_default=None)
    op.alter_column("restaurant_expenses", "transferred_to_statement", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_rest_expenses_transferred", table_name="restaurant_expenses")
    op.drop_column("restaurant_expenses", "transferred_to_statement")
    op.drop_column("restaurant_expenses", "operation_type")
