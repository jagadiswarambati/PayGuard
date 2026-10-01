from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum, Float, ForeignKey, Text, Boolean
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

    # Dates
    invoice_date = Column(DateTime, nullable=False)
    due_date = Column(DateTime)

    # Currency
    currency = Column(String, default="INR")

    # Indian tax breakdown
    subtotal = Column(Float, nullable=False, default=0.0)      # Taxable value
    cgst_amount = Column(Float, default=0.0)                   # Central GST (intrastate)
    sgst_amount = Column(Float, default=0.0)                   # State GST (intrastate)
    igst_amount = Column(Float, default=0.0)                   # Integrated GST (interstate)
    tax_amount = Column(Float, default=0.0)                    # Total GST (cgst+sgst or igst)
    total_amount = Column(Float, nullable=False, default=0.0)  # Taxable + GST
    discount_amount = Column(Float, default=0.0)

    # GST transaction type
    intra_state = Column(Boolean, default=False)               # True = CGST+SGST, False = IGST
    place_of_supply = Column(String)                           # State of supply

    # Vendor GST info (from invoice)
    vendor_gstin = Column(String)                              # Vendor's GSTIN on invoice
    buyer_gstin = Column(String)                               # Buyer's GSTIN on invoice

    # Terms & reference
    payment_terms = Column(String)
    status = Column(SQLEnum(InvoiceStatus), default=InvoiceStatus.RECEIVED)
    source_file = Column(String)
    nova_invoice_id = Column(String, index=True)               # NOVA API reference ID
    extraction_confidence = Column(Float, default=1.0)

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
    hsn_sac_code = Column(String)                              # HSN (goods) or SAC (services)
    quantity = Column(Float, nullable=False, default=1.0)
    unit_price = Column(Float, nullable=False, default=0.0)
    taxable_value = Column(Float, default=0.0)
    gst_rate = Column(Float, default=0.0)                      # GST % (e.g. 18.0)
    cgst_rate = Column(Float, default=0.0)
    sgst_rate = Column(Float, default=0.0)
    igst_rate = Column(Float, default=0.0)
    gst_amount = Column(Float, default=0.0)                    # GST on this line
    tax_rate = Column(Float, default=0.0)                      # Legacy field (= gst_rate/100)
    line_total = Column(Float, nullable=False, default=0.0)    # taxable_value + gst_amount
    discount = Column(Float, default=0.0)

    # Relationships
    invoice = relationship("Invoice", back_populates="items")
