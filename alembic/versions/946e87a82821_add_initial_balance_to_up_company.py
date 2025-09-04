"""add initial_balance to up_company

Revision ID: 946e87a82821
Revises: 8cbd56814dc3
Create Date: 2025-08-27 14:15:08.694315

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '946e87a82821'
down_revision: Union[str, Sequence[str], None] = '8cbd56814dc3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column('up_company', sa.Column('initial_balance', sa.Numeric(14, 2), nullable=True, server_default="0"))


def downgrade():
    op.drop_column('up_company', 'initial_balance')
