from typing import Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime
from ..models import (
    Invoice, Approval, ApprovalStatus, ApprovalLevel,
    PayableObligation, PaymentStatus,
    AuditEvent, AuditAction, ActorType
)
from ..config import get_settings

settings = get_settings()

class ApprovalEngine:
    def __init__(self, db: Session):
        self.db = db
        self.threshold_low = settings.approval_threshold_low
        self.threshold_medium = settings.approval_threshold_medium
    
    async def determine_approval(self, invoice: Invoice) -> Dict[str, Any]:
        """Determine if approval is required and at what level"""
        
        if invoice.total_amount < self.threshold_low:
            return {
                "requires_approval": False,
                "level": None,
                "reason": "Amount below approval threshold"
            }
        elif invoice.total_amount < self.threshold_medium:
            return {
                "requires_approval": True,
                "level": ApprovalLevel.MEDIUM,
                "reason": f"Amount ${invoice.total_amount:.2f} requires medium-level approval"
            }
        else:
            return {
                "requires_approval": True,
                "level": ApprovalLevel.HIGH,
                "reason": f"Amount ${invoice.total_amount:.2f} requires high-level approval"
            }
    
    async def create_approvals(self, invoice: Invoice, level: ApprovalLevel):
        """Create approval records for invoice"""
        approval = Approval(
            invoice_id=invoice.id,
            level=level,
            status=ApprovalStatus.PENDING
        )
        self.db.add(approval)
        
        # Create audit event
        audit = AuditEvent(
            entity_type="Invoice",
            entity_id=invoice.id,
            action=AuditAction.APPROVAL_REQUESTED,
            actor_type=ActorType.SYSTEM,
            result="APPROVAL_REQUESTED",
            metadata={"level": level.value, "amount": invoice.total_amount}
        )
        self.db.add(audit)
        self.db.commit()
    
    async def create_payable_obligation(self, invoice: Invoice):
        """Create payable obligation for approved invoice"""
        
        # Check if payable already exists
        existing = self.db.query(PayableObligation).filter(
            PayableObligation.invoice_id == invoice.id
        ).first()
        
        if existing:
            return existing
        
        payable = PayableObligation(
            invoice_id=invoice.id,
            vendor_id=invoice.vendor_id,
            amount=invoice.total_amount,
            currency=invoice.currency,
            invoice_date=invoice.invoice_date,
            due_date=invoice.due_date,
            approval_status="APPROVED",
            payment_status=PaymentStatus.UNPAID
        )
        self.db.add(payable)
        
        # Create audit event
        audit = AuditEvent(
            entity_type="PayableObligation",
            entity_id=invoice.id,
            action=AuditAction.PAYABLE_CREATED,
            actor_type=ActorType.SYSTEM,
            result="PAYABLE_CREATED",
            metadata={
                "invoice_id": invoice.id,
                "vendor_id": invoice.vendor_id,
                "amount": invoice.total_amount
            }
        )
        self.db.add(audit)
        self.db.commit()
        
        return payable
