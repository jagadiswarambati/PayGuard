from typing import Dict, Any, List
from sqlalchemy.orm import Session
from datetime import datetime
from ..models import (
    Invoice, InvoiceStatus, Approval, ApprovalStatus, ApprovalLevel,
    PayableObligation, PaymentStatus,
    AuditEvent, AuditAction, ActorType
)
from .settings_service import get_all_settings

class ApprovalEngine:
    def __init__(self, db: Session):
        self.db = db
    
    def _get_thresholds(self):
        settings = get_all_settings(self.db)
        return (
            float(settings.get("approval_threshold_low", 5000.0)),
            float(settings.get("approval_threshold_medium", 25000.0)),
            bool(settings.get("auto_approval_enabled", True))
        )
    
    async def determine_approval(self, invoice: Invoice) -> Dict[str, Any]:
        """Determine required approval levels based on configurable thresholds"""
        thresh_low, thresh_med, auto_enabled = self._get_thresholds()
        amount = invoice.total_amount
        
        if amount < thresh_low and auto_enabled:
            return {
                "requires_approval": False,
                "levels": [],
                "reason": f"Amount (${amount:.2f}) is below approval threshold (${thresh_low:.2f}) - eligible for automatic approval"
            }
        elif amount < thresh_med:
            return {
                "requires_approval": True,
                "levels": [ApprovalLevel.MEDIUM],
                "reason": f"Amount (${amount:.2f}) requires Tier 1 Manager Approval"
            }
        else:
            return {
                "requires_approval": True,
                "levels": [ApprovalLevel.MEDIUM, ApprovalLevel.HIGH],
                "reason": f"High value amount (${amount:.2f} >= ${thresh_med:.2f}) requires Dual Approval Chain: Manager followed by Senior Finance"
            }
    
    async def create_approvals(self, invoice: Invoice, levels: List[ApprovalLevel]):
        """Create sequential or multi-tier approval records for an invoice"""
        # Remove any existing pending approvals
        self.db.query(Approval).filter(
            Approval.invoice_id == invoice.id,
            Approval.status == ApprovalStatus.PENDING
        ).delete()
        
        for idx, level in enumerate(levels):
            approval = Approval(
                invoice_id=invoice.id,
                level=level,
                status=ApprovalStatus.PENDING
            )
            self.db.add(approval)
            self.db.flush()
            
            audit = AuditEvent(
                entity_type="Invoice",
                entity_id=invoice.id,
                action=AuditAction.APPROVAL_REQUESTED,
                actor_type=ActorType.SYSTEM,
                result="APPROVAL_REQUESTED",
                event_metadata={
                    "level": level.value,
                    "sequence": idx + 1,
                    "amount": invoice.total_amount
                }
            )
            self.db.add(audit)
        
        self.db.commit()
    
    async def process_approval_decision(
        self,
        approval: Approval,
        approved: bool,
        comment: str = None,
        approver_id: int = None
    ) -> Dict[str, Any]:
        """Process an individual approval decision and enforce approval chain"""
        invoice = approval.invoice
        approval.comment = comment
        approval.approver_id = approver_id
        approval.approved_at = datetime.utcnow()
        
        if not approved:
            approval.status = ApprovalStatus.REJECTED
            invoice.status = InvoiceStatus.REJECTED
            
            audit = AuditEvent(
                entity_type="Approval",
                entity_id=approval.id,
                action=AuditAction.REJECTED,
                actor_type=ActorType.USER,
                actor_id=approver_id,
                result="REJECTED",
                event_metadata={
                    "invoice_id": invoice.id,
                    "level": approval.level.value,
                    "comment": comment
                }
            )
            self.db.add(audit)
            self.db.commit()
            return {"status": "rejected", "invoice_status": invoice.status.value}
        
        approval.status = ApprovalStatus.APPROVED
        audit = AuditEvent(
            entity_type="Approval",
            entity_id=approval.id,
            action=AuditAction.APPROVED,
            actor_type=ActorType.USER,
            actor_id=approver_id,
            result="APPROVED",
            event_metadata={
                "invoice_id": invoice.id,
                "level": approval.level.value,
                "comment": comment
            }
        )
        self.db.add(audit)
        
        # Check if all approvals for this invoice are completed
        remaining_pending = self.db.query(Approval).filter(
            Approval.invoice_id == invoice.id,
            Approval.status == ApprovalStatus.PENDING
        ).count()
        
        if remaining_pending == 0:
            # Entire approval chain is completed!
            invoice.status = InvoiceStatus.APPROVED
            payable = await self.create_payable_obligation(invoice)
            self.db.commit()
            return {
                "status": "fully_approved",
                "invoice_status": invoice.status.value,
                "payable_id": payable.id if payable else None
            }
        else:
            # Still waiting on next level in chain
            invoice.status = InvoiceStatus.PENDING_REVIEW
            self.db.commit()
            return {
                "status": "partial_approved",
                "invoice_status": invoice.status.value,
                "remaining_approvals": remaining_pending
            }
    
    async def create_payable_obligation(self, invoice: Invoice):
        """Create payable obligation for an approved invoice"""
        existing = self.db.query(PayableObligation).filter(
            PayableObligation.invoice_id == invoice.id
        ).first()
        
        if existing:
            return existing
        
        payable = PayableObligation(
            invoice_id=invoice.id,
            vendor_id=invoice.vendor_id,
            amount=invoice.total_amount,
            currency=invoice.currency or "USD",
            invoice_date=invoice.invoice_date,
            due_date=invoice.due_date,
            approval_status="APPROVED",
            payment_status=PaymentStatus.UNPAID
        )
        self.db.add(payable)
        self.db.flush()
        
        audit = AuditEvent(
            entity_type="PayableObligation",
            entity_id=payable.id,
            action=AuditAction.PAYABLE_CREATED,
            actor_type=ActorType.SYSTEM,
            result="PAYABLE_CREATED",
            event_metadata={
                "invoice_id": invoice.id,
                "vendor_id": invoice.vendor_id,
                "amount": invoice.total_amount,
                "currency": invoice.currency
            }
        )
        self.db.add(audit)
        self.db.commit()
        return payable
