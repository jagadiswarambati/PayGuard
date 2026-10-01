from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum, Float
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from ..database import Base


class VendorStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    BLOCKED = "BLOCKED"


class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(Integer, primary_key=True, index=True)
    vendor_code = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False, index=True)

    # Indian tax identifiers
    gstin = Column(String, index=True)          # GSTIN (15-char GST Identification Number)
    pan = Column(String)                         # PAN (10-char Permanent Account Number)
    tax_id = Column(String)                      # Generic tax ID / legacy field

    # Contact & address
    email = Column(String)
    phone = Column(String)
    address = Column(String)
    city = Column(String)
    state = Column(String)
    state_code = Column(String)                  # 2-digit state code for GST

    # Banking
    bank_ifsc = Column(String)
    bank_account_last4 = Column(String)

    # Vendor metadata
    category = Column(String)                    # e.g. IT Hardware, Logistics
    status = Column(SQLEnum(VendorStatus), default=VendorStatus.ACTIVE)
    payment_terms = Column(String, default="Net 30")
    payment_terms_days = Column(Integer, default=30)
    nova_vendor_id = Column(String, unique=True, index=True)  # NOVA API reference

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    purchase_orders = relationship("PurchaseOrder", back_populates="vendor")
    invoices = relationship("Invoice", back_populates="vendor")
    payable_obligations = relationship("PayableObligation", back_populates="vendor")
