"""add settlement account matching for company and bank operations

Revision ID: add_company_accounts_20260330
Revises: add_perf_indexes_20260309
Create Date: 2026-03-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_company_accounts_20260330"
down_revision: Union[str, Sequence[str], None] = "add_perf_indexes_20260309"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("company", sa.Column("settlement_account", sa.String(), nullable=True))
    op.add_column("statements", sa.Column("payer_account", sa.String(), nullable=True))
    op.add_column("statements", sa.Column("receiver_account", sa.String(), nullable=True))
    op.add_column("editbank", sa.Column("payer_account", sa.String(), nullable=True))
    op.add_column("editbank", sa.Column("receiver_account", sa.String(), nullable=True))

    op.execute("ALTER TABLE company DROP CONSTRAINT IF EXISTS company_inn_key")
    op.execute("DROP INDEX IF EXISTS ix_company_inn")
    op.create_index("ix_company_inn", "company", ["inn"], unique=False)
    op.create_index("ix_company_settlement_account", "company", ["settlement_account"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_company_settlement_account", table_name="company")
    op.drop_column("editbank", "receiver_account")
    op.drop_column("editbank", "payer_account")
    op.drop_column("statements", "receiver_account")
    op.drop_column("statements", "payer_account")
    op.drop_column("company", "settlement_account")

    op.execute("DROP INDEX IF EXISTS ix_company_inn")
    op.create_index("ix_company_inn", "company", ["inn"], unique=True)
