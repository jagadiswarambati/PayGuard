from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from ..database import get_db
from ..models import (
    Approval, ApprovalStatus, Invoice, InvoiceStatus,
    AuditEvent, AuditAction, ActorType
)
from ..services import ApprovalEngine

router = APIRouter(prefix="/api/approvals", tags=["approvals"])

class ApprovalDecision(BaseModel):
    comment: Optional[str] = None
    approver_name: Optional[str] = "Finance Manager"
    approver_id: Optional[int] = 1

class ApprovalReject(BaseModel):
    comment: str = Field(..., min_length=3, description="Mandatory rejection reason")
    approver_name: Optional[str] = "Finance Manager"
    approver_id: Optional[int] = 1

@router.get("")
async def list_approvals(
    status: Optional[str] = None,
    level: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all approvals with optional status and level filters"""
    query = db.query(Approval)
    
    if status:
        query = query.filter(Approval.status == status)
    if level:
        query = query.filter(Approval.level == level)
    
    approvals = query.order_by(Approval.created_at.desc()).offset(skip).limit(limit).all()
    
    return [
        {
            "id": app.id,
            "invoice_id": app.invoice_id,
            "invoice_number": app.invoice.invoice_number if app.invoice else None,
            "vendor_name": app.invoice.vendor.name if (app.invoice and app.invoice.vendor) else (app.invoice.raw_vendor_name if app.invoice else "Unknown"),
            "amount": app.invoice.total_amount if app.invoice else 0.0,
            "currency": app.invoice.currency if app.invoice else "USD",
            "level": app.level.value,
            "status": app.status.value,
            "comment": app.comment,
            "created_at": app.created_at.isoformat(),
            "approved_at": app.approved_at.isoformat() if app.approved_at else None
        }
        for app in approvals
    ]

@router.get("/{approval_id}")
async def get_approval(approval_id: int, db: Session = Depends(get_db)):
    """Get single approval detail"""
    app = db.query(Approval).filter(Approval.id == approval_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Approval not found")
    
    return {
        "id": app.id,
        "invoice_id": app.invoice_id,
        "invoice": {
            "invoice_number": app.invoice.invoice_number if app.invoice else None,
            "vendor_name": app.invoice.vendor.name if (app.invoice and app.invoice.vendor) else app.invoice.raw_vendor_name,
            "amount": app.invoice.total_amount if app.invoice else 0.0,
            "currency": app.invoice.currency if app.invoice else "USD"
        } if app.invoice else None,
        "level": app.level.value,
        "status": app.status.value,
        "comment": app.comment,
        "created_at": app.created_at.isoformat(),
        "approved_at": app.approved_at.isoformat() if app.approved_at else None
    }

@router.post("/{approval_id}/approve")
async def approve_approval(
    approval_id: int,
    data: ApprovalDecision,
    db: Session = Depends(get_db)
):
    """Approve an invoice through its configured multi-tier approval chain"""
    approval = db.query(Approval).filter(Approval.id == approval_id).first()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    
    if approval.status != ApprovalStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"Approval has already been processed as {approval.status.value}")
    
    engine = ApprovalEngine(db)
    result = await engine.process_approval_decision(
        approval=approval,
        approved=True,
        comment=data.comment,
        approver_id=data.approver_id
    )
    
    return {
        "status": result["status"],
        "approval_id": approval.id,
        "invoice_id": approval.invoice_id,
        "invoice_status": result["invoice_status"],
        "payable_id": result.get("payable_id")
    }

@router.post("/{approval_id}/reject")
async def reject_approval(
    approval_id: int,
    data: ApprovalReject,
    db: Session = Depends(get_db)
):
    """Reject an invoice approval"""
    approval = db.query(Approval).filter(Approval.id == approval_id).first()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    
    if approval.status != ApprovalStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"Approval has already been processed as {approval.status.value}")
    
    engine = ApprovalEngine(db)
    result = await engine.process_approval_decision(
        approval=approval,
        approved=False,
        comment=data.comment,
        approver_id=data.approver_id
    )
    
    return {
        "status": "rejected",
        "approval_id": approval.id,
        "invoice_id": approval.invoice_id,
        "invoice_status": result["invoice_status"]
    }
