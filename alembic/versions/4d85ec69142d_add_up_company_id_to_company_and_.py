"""add up_company_id to company and relationship

Revision ID: 4d85ec69142d
Revises: 27b25e161b6b
Create Date: 2025-08-08 15:00:12.491165

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4d85ec69142d'
down_revision: Union[str, Sequence[str], None] = '27b25e161b6b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
