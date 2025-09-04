"""add initial_balance to up_company

Revision ID: 2245f6a95ac0
Revises: 946e87a82821
Create Date: 2025-08-27 14:29:47.557371

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2245f6a95ac0'
down_revision: Union[str, Sequence[str], None] = '946e87a82821'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('statements', sa.Column('paid_for_company_id', sa.Integer(), nullable=True))
    op.create_index('ix_statements_paid_for_company_id', 'statements', ['paid_for_company_id'])
    op.create_foreign_key(None, 'statements', 'company', ['paid_for_company_id'], ['id'])

    op.add_column('income_expense', sa.Column('paid_for_company_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'income_expense', 'company', ['paid_for_company_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint(None, 'income_expense', type_='foreignkey')
    op.drop_column('income_expense', 'paid_for_company_id')

    op.drop_constraint(None, 'statements', type_='foreignkey')
    op.drop_index('ix_statements_paid_for_company_id', table_name='statements')
    op.drop_column('statements', 'paid_for_company_id')
