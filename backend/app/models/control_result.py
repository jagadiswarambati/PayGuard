from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from ..database import Base

class ControlStatus(str, enum.Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"
    REVIEW = "REVIEW"

class ControlSeverity(str, enum.Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class ControlResult(Base):
    __tablename__ = "control_results"
    
    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    control_name = Column(String, nullable=False)
    status = Column(SQLEnum(ControlStatus), nullable=False)
    severity = Column(SQLEnum(ControlSeverity), default=ControlSeverity.NONE)
    message = Column(String)
    details = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    invoice = relationship("Invoice", back_populates="control_results")
