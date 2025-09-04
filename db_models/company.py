from sqlalchemy import Column, Integer, String, Float, Boolean, Date, ForeignKey
from sqlalchemy.orm import relationship
from db_models.base import Base

class Company(Base):
    __tablename__ = "company"

    id = Column(Integer, primary_key=True, autoincrement=True)
    inn = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)  # нормализованное название
    up_company_id = Column(Integer, ForeignKey("up_company.id"), index=True, nullable=True)  # FK вместо названия
    up_company = relationship("UpCompany", back_populates="companies")  # двусторонняя связь