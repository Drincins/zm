from sqlalchemy import Boolean, Column, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from db_models.base import Base


class PaymentMethod(Base):
    __tablename__ = "payment_methods"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    description = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    participates_in_daily = Column(Boolean, nullable=False, default=True, comment="Участвует в дневном учёте")

    expenses = relationship("RestaurantExpense", back_populates="payment_method")
    company_links = relationship(
        "RestaurantPaymentMethod",
        back_populates="payment_method",
        cascade="all,delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("name", name="uq_payment_methods_name"),
    )
