"""add report_year to statements and normalize report_month to month name

Revision ID: add_report_year_to_statements
Revises: add_status_payment_links
Create Date: 2025-12-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_report_year_to_statements"
down_revision: Union[str, Sequence[str], None] = "add_status_payment_links"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


RU_MONTHS = [
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
]
_NAME_TO_IDX = {name.lower(): idx + 1 for idx, name in enumerate(RU_MONTHS)}


def _normalize_month_year(rm: str | None, dt_val) -> tuple[str | None, int]:
    """Returns (month_name, year_int) using rm if possible, else date, else defaults."""
    default_year = 2025
    month_name = None
    year_val: int | None = None

    if rm:
        raw = str(rm).strip()
        # YYYY-MM
        if len(raw) == 7 and raw[4] == "-" and raw[:4].isdigit() and raw[5:].isdigit():
            year_val = int(raw[:4])
            month_idx = int(raw[5:])
            if 1 <= month_idx <= 12:
                month_name = RU_MONTHS[month_idx - 1]
        else:
            parts = raw.split()
            if len(parts) >= 2 and parts[-1].isdigit():
                # "Ноябрь 2025"
                year_val = int(parts[-1])
                month_part = " ".join(parts[:-1]).strip()
                if month_part.lower() in _NAME_TO_IDX:
                    month_name = RU_MONTHS[_NAME_TO_IDX[month_part.lower()] - 1]
                else:
                    month_name = month_part or None
            elif raw.lower() in _NAME_TO_IDX:
                month_name = RU_MONTHS[_NAME_TO_IDX[raw.lower()] - 1]
            else:
                month_name = raw or None

    if year_val is None:
        if dt_val is not None:
            try:
                year_val = int(dt_val.year)
            except Exception:
                year_val = default_year
        else:
            year_val = default_year

    if not month_name:
        if dt_val is not None:
            try:
                month_idx = int(dt_val.month)
                month_name = RU_MONTHS[month_idx - 1]
            except Exception:
                month_name = None

    return month_name, year_val


def upgrade() -> None:
    op.add_column("statements", sa.Column("report_year", sa.Integer(), nullable=True))

    conn = op.get_bind()
    stmt_tbl = sa.table(
        "statements",
        sa.column("id", sa.Integer),
        sa.column("report_month", sa.String),
        sa.column("report_year", sa.Integer),
        sa.column("date", sa.Date),
    )

    rows = conn.execute(sa.select(stmt_tbl.c.id, stmt_tbl.c.report_month, stmt_tbl.c.date)).fetchall()
    for rid, rm, dt_val in rows:
        month_name, year_val = _normalize_month_year(rm, dt_val)
        conn.execute(
            stmt_tbl.update()
            .where(stmt_tbl.c.id == rid)
            .values(report_month=month_name, report_year=year_val)
        )


def downgrade() -> None:
    op.drop_column("statements", "report_year")
