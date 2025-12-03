"""Add income formats and records tables.

Revision ID: ba4c4b8f6db7
Revises: zzz_ondelete_statements_fk
Create Date: 2025-10-10 12:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "ba4c4b8f6db7"
down_revision: Union[str, Sequence[str], None] = "zzz_ondelete_statements_fk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "income_formats",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("code", name="uq_income_formats_code"),
    )

    op.create_table(
        "income_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("report_month", sa.String(length=7), nullable=False),
        sa.Column("up_company_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("format_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("comment", sa.String(), nullable=True),
        sa.Column("recorded", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["up_company_id"], ["up_company.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["format_id"], ["income_formats.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "date",
            "up_company_id",
            "company_id",
            "format_id",
            name="uq_income_records_day_company_format",
        ),
    )
    op.create_index("ix_income_records_report_month", "income_records", ["report_month"])
    op.create_index("ix_income_records_up_company_date", "income_records", ["up_company_id", "date"])

    income_formats_table = sa.table(
        "income_formats",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(
        income_formats_table,
        [
            {"code": "cash", "name": "Наличные", "description": "Выручка (наличные)", "is_active": True},
            {"code": "cards_ooo", "name": "Кредитные карты ООО", "description": "Выручка (карты ООО)", "is_active": True},
            {"code": "cards_ip", "name": "Кредитные карты ИП", "description": "Выручка (карты ИП)", "is_active": True},
            {"code": "payment_link", "name": "Платёжная ссылка", "description": "Выручка (платёжная ссылка)", "is_active": True},
            {"code": "certificates", "name": "Сертификаты / подарочные", "description": "Выручка (сертификаты)", "is_active": True},
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_income_records_up_company_date", table_name="income_records")
    op.drop_index("ix_income_records_report_month", table_name="income_records")
    op.drop_table("income_records")
    op.drop_table("income_formats")
