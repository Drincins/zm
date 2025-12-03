from sqlalchemy import Column, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from db_models.base import Base


class UserCategory(Base):
    __tablename__ = "user_categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False)

    user = relationship("User", back_populates="category_links")
    category = relationship("Category")

    __table_args__ = (
        UniqueConstraint("user_id", "category_id", name="uq_user_category_pair"),
    )
