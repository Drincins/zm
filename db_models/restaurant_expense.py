from sqlalchemy import Boolean, Column, Date, ForeignKey, Integer, Numeric, String, Index
from sqlalchemy.orm import relationship

from db_models.base import Base


class RestaurantExpense(Base):
    __tablename__ = "restaurant_expenses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    report_month = Column(String(7), nullable=False)
    up_company_id = Column(Integer, ForeignKey("up_company.id", ondelete="CASCADE"), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="SET NULL"), nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    payment_method_id = Column(Integer, ForeignKey("payment_methods.id", ondelete="SET NULL"), nullable=True)
    operation_type = Column(String(20), nullable=False, default="списание")
    amount = Column(Numeric(14, 2), nullable=False)
    purpose = Column(String, nullable=True)
    comment = Column(String, nullable=True)
    recorded = Column(Boolean, nullable=False, default=False)
    transferred_to_statement = Column(Boolean, nullable=False, default=False)

    up_company = relationship("UpCompany", foreign_keys=[up_company_id])
    group = relationship("Group", foreign_keys=[group_id])
    category = relationship("Category", foreign_keys=[category_id])
    payment_method = relationship("PaymentMethod", foreign_keys=[payment_method_id], back_populates="expenses")

    __table_args__ = (
        Index("ix_rest_expenses_up_company_month", "up_company_id", "report_month"),
        Index("ix_rest_expenses_up_company_date", "up_company_id", "date"),
        Index("ix_rest_expenses_group", "group_id"),
        Index("ix_rest_expenses_category", "category_id"),
        Index("ix_rest_expenses_payment_method", "payment_method_id"),
        Index("ix_rest_expenses_transferred", "transferred_to_statement"),
    )
