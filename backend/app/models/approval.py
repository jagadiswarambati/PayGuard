from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from ..database import Base

class ApprovalStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class ApprovalLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class Approval(Base):
    __tablename__ = "approvals"
    
    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    approver_id = Column(Integer)
    level = Column(SQLEnum(ApprovalLevel), nullable=False)
    status = Column(SQLEnum(ApprovalStatus), default=ApprovalStatus.PENDING)
    comment = Column(Text)
    approved_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    invoice = relationship("Invoice", back_populates="approvals")
