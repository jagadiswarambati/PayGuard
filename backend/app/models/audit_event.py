from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum, JSON
from datetime import datetime
import enum
from ..database import Base

class ActorType(str, enum.Enum):
    USER = "USER"
    SYSTEM = "SYSTEM"

class AuditAction(str, enum.Enum):
    INVOICE_UPLOADED = "INVOICE_UPLOADED"
    EXTRACTION_STARTED = "EXTRACTION_STARTED"
    EXTRACTION_COMPLETED = "EXTRACTION_COMPLETED"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    VENDOR_VERIFIED = "VENDOR_VERIFIED"
    PO_MATCHED = "PO_MATCHED"
    PO_MISMATCH = "PO_MISMATCH"
    RECEIPT_VERIFIED = "RECEIPT_VERIFIED"
    DUPLICATE_CHECKED = "DUPLICATE_CHECKED"
    FINANCIAL_CHECKED = "FINANCIAL_CHECKED"
    EXCEPTION_CREATED = "EXCEPTION_CREATED"
    EXCEPTION_RESOLVED = "EXCEPTION_RESOLVED"
    EXCEPTION_OVERRIDDEN = "EXCEPTION_OVERRIDDEN"
    EXCEPTION_REASSIGNED = "EXCEPTION_REASSIGNED"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PAYABLE_CREATED = "PAYABLE_CREATED"
    PAYMENT_STATUS_CHANGED = "PAYMENT_STATUS_CHANGED"
    SETTINGS_UPDATED = "SETTINGS_UPDATED"

class AuditEvent(Base):
    __tablename__ = "audit_events"
    
    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String, nullable=False)
    entity_id = Column(Integer, nullable=False)
    action = Column(SQLEnum(AuditAction), nullable=False)
    actor_type = Column(SQLEnum(ActorType), nullable=False)
    actor_id = Column(Integer, nullable=True)
    result = Column(String)
    event_metadata = Column("metadata", JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    def __init__(self, **kwargs):
        if "metadata" in kwargs:
            kwargs["event_metadata"] = kwargs.pop("metadata")
        super().__init__(**kwargs)

    @property
    def meta(self):
        return self.event_metadata or {}

