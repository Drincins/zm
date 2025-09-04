from sqlalchemy import Column, Integer, String, Float, Boolean, Date, ForeignKey
from sqlalchemy.orm import relationship
from db_models.base import Base

class Category(Base):

    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, nullable=True)
    name = Column(String, unique=True, nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)

    group = relationship("Group", back_populates="categories")
    firms = relationship("Firm", back_populates="category")

