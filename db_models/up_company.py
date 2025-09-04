from sqlalchemy import Column, Integer, String, Float, Date
from db_models.base import Base
from sqlalchemy.orm import relationship

class UpCompany(Base):
    __tablename__ = "up_company"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    companies = relationship("Company", back_populates="up_company")
    balance_base_amount = Column(Float, nullable=False, default=0.0)  # зафиксированная база баланса
    balance_base_date   = Column(Date, nullable=True)      