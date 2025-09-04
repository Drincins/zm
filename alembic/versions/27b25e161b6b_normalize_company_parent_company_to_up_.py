"""normalize company parent_company to up_company_id

Revision ID: 27b25e161b6b
Revises: d1c30ceedfbd
Create Date: 2025-08-08 14:35:30.064379

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '27b25e161b6b'
down_revision: Union[str, Sequence[str], None] = 'd1c30ceedfbd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():
    op.add_column('company', sa.Column('up_company_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_company_up_company_id'), 'company', ['up_company_id'], unique=False)
    op.create_foreign_key('fk_company_up_company_id', 'company', 'up_company', ['up_company_id'], ['id'])

    # перенос данных: маппим старое текстовое поле на id up_company по имени
    conn = op.get_bind()
    # 1) читаем справочник up_company: name->id
    up_map = dict(conn.execute(sa.text("SELECT name, id FROM up_company")).fetchall())
    # 2) обновляем company.up_company_id по совпадению названия
    conn.execute(sa.text("""
        UPDATE company c
        SET up_company_id = u.id
        FROM up_company u
        WHERE c.parent_company IS NOT NULL
          AND c.parent_company <> ''
          AND u.name = c.parent_company
    """))

    # удаляем старое поле
    with op.batch_alter_table('company') as batch_op:
        batch_op.drop_column('parent_company')


def downgrade():
    with op.batch_alter_table('company') as batch_op:
        batch_op.add_column(sa.Column('parent_company', sa.String(), nullable=True))

    conn = op.get_bind()
    # обратный перенос: по id восстанавливаем название
    conn.execute(sa.text("""
        UPDATE company c
        SET parent_company = u.name
        FROM up_company u
        WHERE c.up_company_id = u.id
    """))

    op.drop_constraint('fk_company_up_company_id', 'company', type_='foreignkey')
    op.drop_index(op.f('ix_company_up_company_id'), table_name='company')
    with op.batch_alter_table('company') as batch_op:
        batch_op.drop_column('up_company_id')
