from sqlalchemy import Column, Integer, String, Float, Boolean, Date, ForeignKey, event
from sqlalchemy.orm import relationship
from db_models.base import Base
from core.utils import canonical_operation_type, normalize_amount_by_type
from core.parser import clean_inn, clean_account  # очистка ИНН/счета


class EditBank(Base):
    __tablename__ = "editbank"

    id = Column(Integer, primary_key=True, autoincrement=True)
    row_id = Column(String, unique=True, index=True, nullable=False)
    date = Column(Date, nullable=False)
    report_month = Column(String, index=True)
    doc_number = Column(String)
    payer_inn = Column(String)
    receiver_inn = Column(String)
    payer_account = Column(String)
    receiver_account = Column(String)
    purpose = Column(String)
    amount = Column(Float)
    operation_type = Column(String, index=True)
    comment = Column(String)
    recorded = Column(Boolean, default=False, index=True)
    manually_edited = Column(Boolean, default=False)
    parent_company = Column(String)
    payer_raw = Column(String)
    receiver_raw = Column(String)

    # FK
    payer_company_id    = Column(Integer, ForeignKey('company.id'),   nullable=True)
    payer_firm_id       = Column(Integer, ForeignKey('firms.id'),     nullable=True)
    receiver_company_id = Column(Integer, ForeignKey('company.id'),   nullable=True)
    receiver_firm_id    = Column(Integer, ForeignKey('firms.id'),     nullable=True)
    up_company_id       = Column(Integer, ForeignKey('up_company.id'), index=True)
    group_id            = Column(Integer, ForeignKey('groups.id'),      index=True)
    category_id         = Column(Integer, ForeignKey('categories.id'),   index=True)

    # NEW: "За кого платили" — по умолчанию = up_company_id
    za_kogo_platili_id  = Column(Integer, ForeignKey('up_company.id'), index=True, nullable=True)

    # Relationships
    payer_firm        = relationship('Firm',     foreign_keys=[payer_firm_id])
    receiver_firm     = relationship('Firm',     foreign_keys=[receiver_firm_id])
    payer_company     = relationship('Company',  foreign_keys=[payer_company_id])
    receiver_company  = relationship('Company',  foreign_keys=[receiver_company_id])
    group_obj         = relationship('Group',    foreign_keys=[group_id])
    category_obj      = relationship('Category', foreign_keys=[category_id])
    za_kogo_platili   = relationship('UpCompany', foreign_keys=[za_kogo_platili_id])  # NEW


# --- Авто-нормализация/очистка и дефолты перед записью в БД ---
@event.listens_for(EditBank, "before_insert")
def _eb_before_insert(mapper, connection, target):
    target.operation_type = canonical_operation_type(getattr(target, "operation_type", None))
    # приведение суммы в соответствии с типом операции
    target.amount = normalize_amount_by_type(target.operation_type, target.amount)
    # очистка ИНН
    target.payer_inn = clean_inn(getattr(target, "payer_inn", None))
    target.receiver_inn = clean_inn(getattr(target, "receiver_inn", None))
    target.payer_account = clean_account(getattr(target, "payer_account", None))
    target.receiver_account = clean_account(getattr(target, "receiver_account", None))
    # NEW: по умолчанию «за кого платили» = головная компания операции
    if getattr(target, "za_kogo_platili_id", None) is None:
        target.za_kogo_platili_id = getattr(target, "up_company_id", None)


@event.listens_for(EditBank, "before_update")
def _eb_before_update(mapper, connection, target):
    target.operation_type = canonical_operation_type(getattr(target, "operation_type", None))
    # приведение суммы в соответствии с типом операции
    target.amount = normalize_amount_by_type(target.operation_type, target.amount)
    # очистка ИНН
    target.payer_inn = clean_inn(getattr(target, "payer_inn", None))
    target.receiver_inn = clean_inn(getattr(target, "receiver_inn", None))
    target.payer_account = clean_account(getattr(target, "payer_account", None))
    target.receiver_account = clean_account(getattr(target, "receiver_account", None))
    # NEW: если поле пустое — подставляем головную
    if getattr(target, "za_kogo_platili_id", None) is None:
        target.za_kogo_platili_id = getattr(target, "up_company_id", None)
