from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, text
from sqlalchemy.orm import relationship

from db_models.base import Base


class Company(Base):
    __tablename__ = "company"

    id = Column(Integer, primary_key=True, autoincrement=True)
    inn = Column(String, index=True, nullable=False)
    settlement_account = Column(String, unique=True, index=True, nullable=True)
    name = Column(String, nullable=False)
    up_company_id = Column(Integer, ForeignKey("up_company.id"), index=True, nullable=True)
    is_primary = Column(Boolean, nullable=False, default=False, server_default=text("false"))

    is_active = Column(Boolean, nullable=False, default=True, server_default=text("true"))  # <-- ДОБАВИТЬ

    up_company = relationship("UpCompany", back_populates="companies")
