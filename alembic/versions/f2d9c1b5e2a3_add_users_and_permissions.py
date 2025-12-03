"""Add users, user_companies and user_categories tables.

Revision ID: f2d9c1b5e2a3
Revises: bc1c99c5a64d
Create Date: 2025-11-18 01:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2d9c1b5e2a3"
down_revision: Union[str, Sequence[str], None] = "bc1c99c5a64d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(length=128), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="admin"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "user_companies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("up_company_id", sa.Integer(), sa.ForeignKey("up_company.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("user_id", "up_company_id", name="uq_user_company_pair"),
    )

    op.create_table(
        "user_categories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("user_id", "category_id", name="uq_user_category_pair"),
    )


def downgrade() -> None:
    op.drop_table("user_categories")
    op.drop_table("user_companies")
    op.drop_table("users")
