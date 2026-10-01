from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum
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
    name = Column(String, nullable=False)
    tax_id = Column(String)
    email = Column(String)
    status = Column(SQLEnum(VendorStatus), default=VendorStatus.ACTIVE)
    payment_terms = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    purchase_orders = relationship("PurchaseOrder", back_populates="vendor")
    invoices = relationship("Invoice", back_populates="vendor")
    payable_obligations = relationship("PayableObligation", back_populates="vendor")
