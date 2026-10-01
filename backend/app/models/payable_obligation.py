from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum, Float, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from ..database import Base

class PaymentStatus(str, enum.Enum):
    UNPAID = "UNPAID"
    SCHEDULED = "SCHEDULED"
    PAID = "PAID"
    ON_HOLD = "ON_HOLD"

class PayableObligation(Base):
    __tablename__ = "payable_obligations"
    
    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), unique=True, nullable=False)
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    invoice_date = Column(DateTime, nullable=False)
    due_date = Column(DateTime)
    approval_status = Column(String, default="APPROVED")
    payment_status = Column(SQLEnum(PaymentStatus), default=PaymentStatus.UNPAID)
    payment_reference = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    invoice = relationship("Invoice", back_populates="payable_obligation")
    vendor = relationship("Vendor", back_populates="payable_obligations")
