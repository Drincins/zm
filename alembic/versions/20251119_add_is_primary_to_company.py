"""add is_primary to company

Revision ID: add_is_primary_company
Revises: 64328593bc10_add_balance_base__to_up_company_drop_
Create Date: 2025-11-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_is_primary_company"
down_revision: Union[str, Sequence[str], None] = "f2d9c1b5e2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "company",
        sa.Column(
            "is_primary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.execute("UPDATE company SET is_primary = false WHERE is_primary IS NULL")
    op.alter_column("company", "is_primary", server_default=None)


def downgrade() -> None:
    op.drop_column("company", "is_primary")
