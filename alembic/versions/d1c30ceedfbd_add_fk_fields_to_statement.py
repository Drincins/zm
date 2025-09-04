"""create editbank table

Revision ID: d1c30ceedfbd
Revises: 9f69fc2a208b
Create Date: 2025-08-06 20:46:33.294821

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd1c30ceedfbd'
down_revision: Union[str, Sequence[str], None] = '9f69fc2a208b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        'editbank',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('row_id', sa.String(), unique=True, index=True, nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('report_month', sa.String()),
        sa.Column('doc_number', sa.String()),
        sa.Column('payer_inn', sa.String()),
        sa.Column('receiver_inn', sa.String()),
        sa.Column('purpose', sa.String()),
        sa.Column('amount', sa.Float()),
        sa.Column('operation_type', sa.String()),
        sa.Column('comment', sa.String()),
        sa.Column('recorded', sa.Boolean(), default=False),
        sa.Column('manually_edited', sa.Boolean(), default=False),
        sa.Column('parent_company', sa.String()),
        sa.Column('payer_raw', sa.String()),
        sa.Column('receiver_raw', sa.String()),
        sa.Column('payer_company_id', sa.Integer(), sa.ForeignKey('company.id'), nullable=True),
        sa.Column('payer_firm_id', sa.Integer(), sa.ForeignKey('firms.id'), nullable=True),
        sa.Column('receiver_company_id', sa.Integer(), sa.ForeignKey('company.id'), nullable=True),
        sa.Column('receiver_firm_id', sa.Integer(), sa.ForeignKey('firms.id'), nullable=True),
        sa.Column('up_company_id', sa.Integer(), sa.ForeignKey('up_company.id'), index=True),
        sa.Column('group_id', sa.Integer(), sa.ForeignKey('groups.id'), index=True),
        sa.Column('category_id', sa.Integer(), sa.ForeignKey('categories.id'), index=True)
    )

def downgrade() -> None:
    op.drop_table('editbank')
