"""Create up_company table

Revision ID: c19c5b93a784
Revises: 572f36f0a32e
Create Date: 2025-08-01 18:13:58.064805

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c19c5b93a784'
down_revision: Union[str, Sequence[str], None] = '572f36f0a32e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
