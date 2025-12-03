from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import relationship

from db_models.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(128), unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String(32), nullable=False, default="admin")
    is_active = Column(Boolean, nullable=False, default=True)

    company_links = relationship(
        "UserCompany",
        back_populates="user",
        cascade="all,delete-orphan",
    )
    category_links = relationship(
        "UserCategory",
        back_populates="user",
        cascade="all,delete-orphan",
    )
