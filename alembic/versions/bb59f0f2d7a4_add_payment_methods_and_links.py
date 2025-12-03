"""Add payment methods and link to restaurant expenses.

Revision ID: bb59f0f2d7a4
Revises: ba6f51b70f5a
Create Date: 2025-10-24 19:25:42
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "bb59f0f2d7a4"
down_revision: Union[str, Sequence[str], None] = "ba6f51b70f5a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "payment_methods",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("name", name="uq_payment_methods_name"),
    )

    op.add_column("restaurant_expenses", sa.Column("group_id", sa.Integer(), nullable=True))
    op.add_column("restaurant_expenses", sa.Column("category_id", sa.Integer(), nullable=True))
    op.add_column("restaurant_expenses", sa.Column("payment_method_id", sa.Integer(), nullable=True))

    op.create_foreign_key(
        "restaurant_expenses_group_id_fkey",
        "restaurant_expenses",
        "groups",
        ["group_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "restaurant_expenses_category_id_fkey",
        "restaurant_expenses",
        "categories",
        ["category_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "restaurant_expenses_payment_method_id_fkey",
        "restaurant_expenses",
        "payment_methods",
        ["payment_method_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_index("ix_rest_expenses_group", "restaurant_expenses", ["group_id"])
    op.create_index("ix_rest_expenses_category", "restaurant_expenses", ["category_id"])
    op.create_index("ix_rest_expenses_payment_method", "restaurant_expenses", ["payment_method_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_rest_expenses_payment_method", table_name="restaurant_expenses")
    op.drop_index("ix_rest_expenses_category", table_name="restaurant_expenses")
    op.drop_index("ix_rest_expenses_group", table_name="restaurant_expenses")

    op.drop_constraint("restaurant_expenses_payment_method_id_fkey", "restaurant_expenses", type_="foreignkey")
    op.drop_constraint("restaurant_expenses_category_id_fkey", "restaurant_expenses", type_="foreignkey")
    op.drop_constraint("restaurant_expenses_group_id_fkey", "restaurant_expenses", type_="foreignkey")

    op.drop_column("restaurant_expenses", "payment_method_id")
    op.drop_column("restaurant_expenses", "category_id")
    op.drop_column("restaurant_expenses", "group_id")

    op.drop_table("payment_methods")
