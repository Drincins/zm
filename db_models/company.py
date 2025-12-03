from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from db_models.base import Base


class Company(Base):
    __tablename__ = "company"

    id = Column(Integer, primary_key=True, autoincrement=True)
    inn = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)  # Название компании
    up_company_id = Column(Integer, ForeignKey("up_company.id"), index=True, nullable=True)  # FK головной компании
    is_primary = Column(Boolean, nullable=False, default=False, server_default="false")  # Признак основной для группы

    up_company = relationship("UpCompany", back_populates="companies")  # ������������ �����
