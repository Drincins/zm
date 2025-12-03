from sqlalchemy import Boolean, Column, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from db_models.base import Base


class RestaurantPaymentMethod(Base):
    __tablename__ = "restaurant_payment_methods"

    id = Column(Integer, primary_key=True, autoincrement=True)
    up_company_id = Column(Integer, ForeignKey("up_company.id", ondelete="CASCADE"), nullable=False)
    payment_method_id = Column(Integer, ForeignKey("payment_methods.id", ondelete="CASCADE"), nullable=False)
    is_default = Column(Boolean, nullable=False, default=False)

    up_company = relationship("UpCompany", back_populates="restaurant_payment_methods")
    payment_method = relationship("PaymentMethod", back_populates="company_links")

    __table_args__ = (
        UniqueConstraint("up_company_id", "payment_method_id", name="uq_restaurant_payment_methods_pair"),
    )
