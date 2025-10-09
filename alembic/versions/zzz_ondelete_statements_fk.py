"""
Adjust ON DELETE policies for statements foreign keys.

Revision ID: zzz_ondelete_statements_fk
Revises: 
Create Date: 2025-10-09
"""
from alembic import op
import sqlalchemy as sa


revision = 'zzz_ondelete_statements_fk'
down_revision = '2245f6a95ac0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use raw SQL to be resilient to unknown existing constraint names
    # Postgres default names are <table>_<column>_fkey
    stmts = [
        "ALTER TABLE statements DROP CONSTRAINT IF EXISTS statements_payer_company_id_fkey;",
        "ALTER TABLE statements ADD CONSTRAINT statements_payer_company_id_fkey FOREIGN KEY (payer_company_id) REFERENCES company(id) ON DELETE SET NULL;",

        "ALTER TABLE statements DROP CONSTRAINT IF EXISTS statements_receiver_company_id_fkey;",
        "ALTER TABLE statements ADD CONSTRAINT statements_receiver_company_id_fkey FOREIGN KEY (receiver_company_id) REFERENCES company(id) ON DELETE SET NULL;",

        "ALTER TABLE statements DROP CONSTRAINT IF EXISTS statements_payer_firm_id_fkey;",
        "ALTER TABLE statements ADD CONSTRAINT statements_payer_firm_id_fkey FOREIGN KEY (payer_firm_id) REFERENCES firms(id) ON DELETE SET NULL;",

        "ALTER TABLE statements DROP CONSTRAINT IF EXISTS statements_receiver_firm_id_fkey;",
        "ALTER TABLE statements ADD CONSTRAINT statements_receiver_firm_id_fkey FOREIGN KEY (receiver_firm_id) REFERENCES firms(id) ON DELETE SET NULL;",

        "ALTER TABLE statements DROP CONSTRAINT IF EXISTS statements_group_id_fkey;",
        "ALTER TABLE statements ADD CONSTRAINT statements_group_id_fkey FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE SET NULL;",

        "ALTER TABLE statements DROP CONSTRAINT IF EXISTS statements_category_id_fkey;",
        "ALTER TABLE statements ADD CONSTRAINT statements_category_id_fkey FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL;",

        "ALTER TABLE statements DROP CONSTRAINT IF EXISTS statements_paid_for_company_id_fkey;",
        "ALTER TABLE statements ADD CONSTRAINT statements_paid_for_company_id_fkey FOREIGN KEY (paid_for_company_id) REFERENCES company(id) ON DELETE SET NULL;",

        "ALTER TABLE statements DROP CONSTRAINT IF EXISTS statements_za_kogo_platili_id_fkey;",
        "ALTER TABLE statements ADD CONSTRAINT statements_za_kogo_platili_id_fkey FOREIGN KEY (za_kogo_platili_id) REFERENCES up_company(id) ON DELETE SET NULL;",

        "ALTER TABLE statements DROP CONSTRAINT IF EXISTS statements_up_company_id_fkey;",
        "ALTER TABLE statements ADD CONSTRAINT statements_up_company_id_fkey FOREIGN KEY (up_company_id) REFERENCES up_company(id) ON DELETE RESTRICT;",
    ]
    for sql in stmts:
        # SQLAlchemy 2.0 requires executable objects; wrap with sa.text
        op.execute(sa.text(sql))


def downgrade() -> None:
    # No-op: leave safer policies in place.
    pass
