"""Add up_company table44

Revision ID: 14b49a5fa3c8
Revises: 21153834a8c0
Create Date: 2025-08-01 18:17:10.831610

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '14b49a5fa3c8'
down_revision: Union[str, Sequence[str], None] = '21153834a8c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'up_company',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('code', sa.String(), nullable=False, unique=True),
        sa.Column('company_id', sa.Integer, sa.ForeignKey('company.id'), nullable=True),
    )

def downgrade() -> None:
    op.drop_table('up_company')
