from sqlalchemy import Column, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from db_models.base import Base


class UserCompany(Base):
    __tablename__ = "user_companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    up_company_id = Column(Integer, ForeignKey("up_company.id", ondelete="CASCADE"), nullable=False)

    user = relationship("User", back_populates="company_links")
    up_company = relationship("UpCompany")

    __table_args__ = (
        UniqueConstraint("user_id", "up_company_id", name="uq_user_company_pair"),
    )
