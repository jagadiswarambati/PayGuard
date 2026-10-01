from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum, Float, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from ..database import Base

class POStatus(str, enum.Enum):
    OPEN = "OPEN"
    PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED"
    RECEIVED = "RECEIVED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"

class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    
    id = Column(Integer, primary_key=True, index=True)
    po_number = Column(String, unique=True, index=True, nullable=False)
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=False)
    po_date = Column(DateTime, nullable=False)
    currency = Column(String, default="USD")
    status = Column(SQLEnum(POStatus), default=POStatus.OPEN)
    total_amount = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    vendor = relationship("Vendor", back_populates="purchase_orders")
    items = relationship("PurchaseOrderItem", back_populates="purchase_order", cascade="all, delete-orphan")
    goods_receipts = relationship("GoodsReceipt", back_populates="purchase_order")
    invoices = relationship("Invoice", back_populates="purchase_order")

class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"
    
    id = Column(Integer, primary_key=True, index=True)
    purchase_order_id = Column(Integer, ForeignKey("purchase_orders.id"), nullable=False)
    description = Column(String, nullable=False)
    sku = Column(String)
    quantity = Column(Float, nullable=False)
    unit_price = Column(Float, nullable=False)
    tax_rate = Column(Float, default=0.0)
    line_total = Column(Float, nullable=False)
    
    # Relationships
    purchase_order = relationship("PurchaseOrder", back_populates="items")
    receipt_items = relationship("GoodsReceiptItem", back_populates="po_item")
