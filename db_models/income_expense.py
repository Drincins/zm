from sqlalchemy import Column, Integer, Date, String, Numeric, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from db_models.base import Base  # общий Base проекта

from db_models import up_company as m_up
from db_models import company as m_company
from db_models import group as m_group
from db_models import category as m_cat

class IncomeExpense(Base):
    __tablename__ = "income_expense"

    id = Column(Integer, primary_key=True, autoincrement=True)

    date = Column(Date, nullable=False)
    report_month = Column(String(7), nullable=False)  # YYYY-MM

    up_company_id = Column(Integer, ForeignKey(m_up.UpCompany.id), nullable=False)
    company_id    = Column(Integer, ForeignKey(m_company.Company.id), nullable=True)
    group_id      = Column(Integer, ForeignKey(m_group.Group.id), nullable=True)
    category_id   = Column(Integer, ForeignKey(m_cat.Category.id), nullable=True)
    paid_for_company_id = Column(Integer, ForeignKey(m_company.Company.id), nullable=True)
    
    operation_type = Column(String(20), nullable=False)  # 'списание' | 'поступление'
    amount = Column(Numeric(14, 2), nullable=False)
    comment = Column(String, nullable=True)

    # (опционально) связи, чтобы джойнить названия при выборках
    up_company = relationship("UpCompany", lazy="joined", foreign_keys=[up_company_id])
    company    = relationship("Company",   lazy="joined", foreign_keys=[company_id])
    group      = relationship("Group",     lazy="joined", foreign_keys=[group_id])
    category   = relationship("Category",  lazy="joined", foreign_keys=[category_id])


    __table_args__ = (
        CheckConstraint("operation_type in ('списание','поступление')", name="ck_income_expense_operation_type"),
    )
