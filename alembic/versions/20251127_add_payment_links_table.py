"""add payment_links table

Revision ID: add_payment_links
Revises: add_purpose_restaurant_expense
Create Date: 2025-11-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_payment_links"
down_revision: Union[str, Sequence[str], None] = "add_purpose_restaurant_expense"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_links",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("up_company_id", sa.Integer(), sa.ForeignKey("up_company.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("booking_date", sa.Date(), nullable=False),
        sa.Column("report_month", sa.String(length=7), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
    )
    op.create_index(
        "ix_payment_links_up_company_month",
        "payment_links",
        ["up_company_id", "report_month"],
        unique=False,
    )
    op.create_index(
        "ix_payment_links_payment_date",
        "payment_links",
        ["payment_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_payment_links_payment_date", table_name="payment_links")
    op.drop_index("ix_payment_links_up_company_month", table_name="payment_links")
    op.drop_table("payment_links")
