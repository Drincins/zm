"""Add restaurant expenses table.

Revision ID: ba6f51b70f5a
Revises: ba4c4b8f6db7
Create Date: 2025-10-24 19:05:44
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "ba6f51b70f5a"
down_revision: Union[str, Sequence[str], None] = "ba4c4b8f6db7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "restaurant_expenses",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("report_month", sa.String(length=7), nullable=False),
        sa.Column("up_company_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("comment", sa.String(), nullable=True),
        sa.Column("recorded", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["up_company_id"], ["up_company.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_rest_expenses_up_company_month",
        "restaurant_expenses",
        ["up_company_id", "report_month"],
    )
    op.create_index(
        "ix_rest_expenses_up_company_date",
        "restaurant_expenses",
        ["up_company_id", "date"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_rest_expenses_up_company_date", table_name="restaurant_expenses")
    op.drop_index("ix_rest_expenses_up_company_month", table_name="restaurant_expenses")
    op.drop_table("restaurant_expenses")
