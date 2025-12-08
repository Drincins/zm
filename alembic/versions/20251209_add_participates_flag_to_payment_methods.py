"""add participates_in_daily to payment_methods

Revision ID: add_participates_flag_payment_methods
Revises: add_report_year_to_statements
Create Date: 2025-12-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_participates_flag_payment_methods"
down_revision: Union[str, Sequence[str], None] = "add_report_year_to_statements"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "payment_methods",
        sa.Column("participates_in_daily", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    # drop default to keep app-side control
    op.alter_column("payment_methods", "participates_in_daily", server_default=None)


def downgrade() -> None:
    op.drop_column("payment_methods", "participates_in_daily")
