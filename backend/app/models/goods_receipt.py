from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum, Float, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from ..database import Base

class ReceiptStatus(str, enum.Enum):
    RECEIVED = "RECEIVED"
    VERIFIED = "VERIFIED"
    CANCELLED = "CANCELLED"

class GoodsReceipt(Base):
    __tablename__ = "goods_receipts"
    
    id = Column(Integer, primary_key=True, index=True)
    receipt_number = Column(String, unique=True, index=True, nullable=False)
    purchase_order_id = Column(Integer, ForeignKey("purchase_orders.id"), nullable=False)
    received_date = Column(DateTime, nullable=False)
    status = Column(SQLEnum(ReceiptStatus), default=ReceiptStatus.RECEIVED)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    purchase_order = relationship("PurchaseOrder", back_populates="goods_receipts")
    items = relationship("GoodsReceiptItem", back_populates="goods_receipt", cascade="all, delete-orphan")

class GoodsReceiptItem(Base):
    __tablename__ = "goods_receipt_items"
    
    id = Column(Integer, primary_key=True, index=True)
    goods_receipt_id = Column(Integer, ForeignKey("goods_receipts.id"), nullable=False)
    po_item_id = Column(Integer, ForeignKey("purchase_order_items.id"), nullable=False)
    quantity_received = Column(Float, nullable=False)
    
    # Relationships
    goods_receipt = relationship("GoodsReceipt", back_populates="items")
    po_item = relationship("PurchaseOrderItem", back_populates="receipt_items")
