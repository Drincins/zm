"""Add up_company table44

Revision ID: 16c7ea815f38
Revises: 14b49a5fa3c8
Create Date: 2025-08-01 18:20:21.159877

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '16c7ea815f38'
down_revision: Union[str, Sequence[str], None] = '14b49a5fa3c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'up_company',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(), nullable=False, unique=True),
    )

def downgrade() -> None:
    op.drop_table('up_company')
