"""add performance indexes for statements and editbank filters

Revision ID: add_perf_indexes_20260309
Revises: add_participates_flag_payment_methods
Create Date: 2026-03-09
"""

from typing import Sequence, Union

from alembic import op


revision: str = "add_perf_indexes_20260309"
down_revision: Union[str, Sequence[str], None] = "add_participates_flag_payment_methods"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # statements
    op.execute("CREATE INDEX IF NOT EXISTS ix_statements_report_month ON statements (report_month)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_statements_report_year ON statements (report_year)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_statements_report_month_year ON statements (report_month, report_year)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_statements_payer_company_id ON statements (payer_company_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_statements_receiver_company_id ON statements (receiver_company_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_statements_recorded ON statements (recorded)")

    # editbank
    op.execute("CREATE INDEX IF NOT EXISTS ix_editbank_report_month ON editbank (report_month)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_editbank_operation_type ON editbank (operation_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_editbank_recorded ON editbank (recorded)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_editbank_recorded")
    op.execute("DROP INDEX IF EXISTS ix_editbank_operation_type")
    op.execute("DROP INDEX IF EXISTS ix_editbank_report_month")

    op.execute("DROP INDEX IF EXISTS ix_statements_recorded")
    op.execute("DROP INDEX IF EXISTS ix_statements_receiver_company_id")
    op.execute("DROP INDEX IF EXISTS ix_statements_payer_company_id")
    op.execute("DROP INDEX IF EXISTS ix_statements_report_month_year")
    op.execute("DROP INDEX IF EXISTS ix_statements_report_year")
    op.execute("DROP INDEX IF EXISTS ix_statements_report_month")
