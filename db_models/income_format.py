from sqlalchemy import Boolean, Column, Integer, Numeric, String, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from db_models.base import Base


class IncomeFormat(Base):
    __tablename__ = "income_formats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    description = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    records = relationship("IncomeRecord", back_populates="format", cascade="all,delete-orphan")


class IncomeRecord(Base):
    __tablename__ = "income_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    report_month = Column(String(7), nullable=False)  # YYYY-MM

    up_company_id = Column(Integer, ForeignKey("up_company.id"), nullable=False)
    company_id = Column(Integer, ForeignKey("company.id"), nullable=True)
    format_id = Column(Integer, ForeignKey("income_formats.id"), nullable=False)

    amount = Column(Numeric(14, 2), nullable=False)
    comment = Column(String, nullable=True)
    recorded = Column(Boolean, nullable=False, default=False)

    format = relationship("IncomeFormat", back_populates="records")
    up_company = relationship("UpCompany", foreign_keys=[up_company_id])
    company = relationship("Company", foreign_keys=[company_id])

    __table_args__ = (
        UniqueConstraint(
            "date",
            "up_company_id",
            "company_id",
            "format_id",
            name="uq_income_records_day_company_format",
        ),
    )
