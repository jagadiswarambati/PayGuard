from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from ..database import Base

class ExceptionType(str, enum.Enum):
    VENDOR_NOT_FOUND = "VENDOR_NOT_FOUND"
    VENDOR_BLOCKED = "VENDOR_BLOCKED"
    PO_NOT_FOUND = "PO_NOT_FOUND"
    PO_VENDOR_MISMATCH = "PO_VENDOR_MISMATCH"
    QUANTITY_MISMATCH = "QUANTITY_MISMATCH"
    PRICE_MISMATCH = "PRICE_MISMATCH"
    RECEIPT_MISSING = "RECEIPT_MISSING"
    RECEIPT_QUANTITY_INSUFFICIENT = "RECEIPT_QUANTITY_INSUFFICIENT"
    DUPLICATE_INVOICE = "DUPLICATE_INVOICE"
    FINANCIAL_MISMATCH = "FINANCIAL_MISMATCH"
    TAX_MISMATCH = "TAX_MISMATCH"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    HIGH_VALUE_APPROVAL = "HIGH_VALUE_APPROVAL"

class ExceptionSeverity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class ExceptionStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_REVIEW = "IN_REVIEW"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"
    OVERRIDDEN = "OVERRIDDEN"

class Exception(Base):
    __tablename__ = "exceptions"
    
    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    type = Column(SQLEnum(ExceptionType), nullable=False)
    severity = Column(SQLEnum(ExceptionSeverity), nullable=False)
    status = Column(SQLEnum(ExceptionStatus), default=ExceptionStatus.OPEN)
    message = Column(String, nullable=False)
    assigned_to = Column(Integer, nullable=True)
    assigned_to_name = Column(String, nullable=True)
    resolution = Column(Text, nullable=True)
    resolution_notes = Column(Text, nullable=True)
    override_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    
    # Relationships
    invoice = relationship("Invoice", back_populates="exceptions")

