"""Add up_company table

Revision ID: 21153834a8c0
Revises: c19c5b93a784
Create Date: 2025-08-01 18:15:50.714948

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '21153834a8c0'
down_revision: Union[str, Sequence[str], None] = 'c19c5b93a784'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
