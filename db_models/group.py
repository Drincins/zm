from sqlalchemy import Column, Integer, String, Float, Boolean, Date, ForeignKey
from sqlalchemy.orm import relationship
from db_models.base import Base

class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, nullable=True)  # можно оставить пустым
    name = Column(String, unique=True, nullable=False)

    categories = relationship("Category", back_populates="group")
