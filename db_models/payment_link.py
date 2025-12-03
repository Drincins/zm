from sqlalchemy import Column, Date, ForeignKey, Integer, Numeric, String, Index
from sqlalchemy.orm import relationship

from db_models.base import Base


class PaymentLink(Base):
    __tablename__ = "payment_links"

    id = Column(Integer, primary_key=True, autoincrement=True)
    up_company_id = Column(Integer, ForeignKey("up_company.id", ondelete="CASCADE"), nullable=False)
    payment_date = Column(Date, nullable=False)
    booking_date = Column(Date, nullable=False)
    report_month = Column(String(7), nullable=False)  # YYYY-MM
    amount = Column(Numeric(14, 2), nullable=False)
    status = Column(String(32), nullable=False, default="received")  # received | booked

    up_company = relationship("UpCompany", foreign_keys=[up_company_id])

    __table_args__ = (
        Index("ix_payment_links_up_company_month", "up_company_id", "report_month"),
        Index("ix_payment_links_payment_date", "payment_date"),
    )
