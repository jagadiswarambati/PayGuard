from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from ..database import Base

class InvoiceStatus(str, enum.Enum):
    RECEIVED = "RECEIVED"
    PROCESSING = "PROCESSING"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ON_HOLD = "ON_HOLD"
    PAID = "PAID"

class Invoice(Base):
    __tablename__ = "invoices"
    
    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String, index=True, nullable=False)
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=True)
    raw_vendor_name = Column(String, nullable=True)
    po_id = Column(Integer, ForeignKey("purchase_orders.id"), nullable=True)

    invoice_date = Column(DateTime, nullable=False)
    due_date = Column(DateTime)
    currency = Column(String, default="USD")
    subtotal = Column(Float, nullable=False)
    tax_amount = Column(Float, default=0.0)
    total_amount = Column(Float, nullable=False)
    payment_terms = Column(String)
    status = Column(SQLEnum(InvoiceStatus), default=InvoiceStatus.RECEIVED)
    source_file = Column(String)
    extraction_confidence = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    vendor = relationship("Vendor", back_populates="invoices")
    purchase_order = relationship("PurchaseOrder", back_populates="invoices")
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    control_results = relationship("ControlResult", back_populates="invoice", cascade="all, delete-orphan")
    exceptions = relationship("Exception", back_populates="invoice", cascade="all, delete-orphan")
    approvals = relationship("Approval", back_populates="invoice", cascade="all, delete-orphan")
    payable_obligation = relationship("PayableObligation", back_populates="invoice", uselist=False)

class InvoiceItem(Base):
    __tablename__ = "invoice_items"
    
    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    description = Column(String, nullable=False)
    sku = Column(String)
    quantity = Column(Float, nullable=False)
    unit_price = Column(Float, nullable=False)
    tax_rate = Column(Float, default=0.0)
    line_total = Column(Float, nullable=False)
    
    # Relationships
    invoice = relationship("Invoice", back_populates="items")
