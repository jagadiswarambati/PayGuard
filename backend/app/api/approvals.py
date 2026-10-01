from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from ..database import get_db
from ..models import (
    Approval, ApprovalStatus, Invoice, InvoiceStatus,
    AuditEvent, AuditAction, ActorType
)
from ..services import ApprovalEngine

router = APIRouter(prefix="/api/approvals", tags=["approvals"])

class ApprovalDecision(BaseModel):
    comment: Optional[str] = None

@router.get("")
async def list_approvals(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all approvals"""
    query = db.query(Approval)
    
    if status:
        query = query.filter(Approval.status == status)
    
    approvals = query.order_by(Approval.created_at.desc()).offset(skip).limit(limit).all()
    
    return [
        {
            "id": app.id,
            "invoice_id": app.invoice_id,
            "invoice_number": app.invoice.invoice_number if app.invoice else None,
            "vendor_name": app.invoice.vendor.name if app.invoice and app.invoice.vendor else None,
            "amount": app.invoice.total_amount if app.invoice else None,
            "level": app.level.value,
            "status": app.status.value,
            "created_at": app.created_at.isoformat(),
            "approved_at": app.approved_at.isoformat() if app.approved_at else None
        }
        for app in approvals
    ]

@router.post("/{approval_id}/approve")
async def approve_approval(
    approval_id: int,
    data: ApprovalDecision,
    db: Session = Depends(get_db)
):
    """Approve an invoice"""
    approval = db.query(Approval).filter(Approval.id == approval_id).first()
    
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    
    if approval.status != ApprovalStatus.PENDING:
        raise HTTPException(status_code=400, detail="Approval already processed")
    
    # Update approval
    approval.status = ApprovalStatus.APPROVED
    approval.comment = data.comment
    approval.approved_at = datetime.utcnow()
    
    # Update invoice status
    invoice = approval.invoice
    invoice.status = InvoiceStatus.APPROVED
    
    # Create payable obligation
    approval_engine = ApprovalEngine(db)
    await approval_engine.create_payable_obligation(invoice)
    
    # Create audit event
    audit = AuditEvent(
        entity_type="Approval",
        entity_id=approval.id,
        action=AuditAction.APPROVED,
        actor_type=ActorType.USER,
        result="APPROVED",
        metadata={
            "invoice_id": invoice.id,
            "amount": invoice.total_amount,
            "comment": data.comment
        }
    )
    db.add(audit)
    db.commit()
    
    return {"status": "approved", "approval_id": approval.id, "invoice_id": invoice.id}

@router.post("/{approval_id}/reject")
async def reject_approval(
    approval_id: int,
    data: ApprovalDecision,
    db: Session = Depends(get_db)
):
    """Reject an invoice approval"""
    approval = db.query(Approval).filter(Approval.id == approval_id).first()
    
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    
    if approval.status != ApprovalStatus.PENDING:
        raise HTTPException(status_code=400, detail="Approval already processed")
    
    # Update approval
    approval.status = ApprovalStatus.REJECTED
    approval.comment = data.comment
    approval.approved_at = datetime.utcnow()
    
    # Update invoice status
    invoice = approval.invoice
    invoice.status = InvoiceStatus.REJECTED
    
    # Create audit event
    audit = AuditEvent(
        entity_type="Approval",
        entity_id=approval.id,
        action=AuditAction.REJECTED,
        actor_type=ActorType.USER,
        result="REJECTED",
        metadata={
            "invoice_id": invoice.id,
            "amount": invoice.total_amount,
            "comment": data.comment
        }
    )
    db.add(audit)
    db.commit()
    
    return {"status": "rejected", "approval_id": approval.id, "invoice_id": invoice.id}
