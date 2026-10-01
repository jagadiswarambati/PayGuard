from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

from ..database import get_db
from ..models import PayableObligation, PaymentStatus, AuditEvent, AuditAction, ActorType

router = APIRouter(prefix="/api/ledger", tags=["ledger"])

class PaymentStatusUpdate(BaseModel):
    payment_status: PaymentStatus
    payment_reference: Optional[str] = None
    note: Optional[str] = None

class RecordPayment(BaseModel):
    payment_reference: str = Field(..., min_length=2, description="Check number, ACH trace, wire ref, etc.")
    note: Optional[str] = None

@router.get("")
async def list_payable_obligations(
    payment_status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all real payable obligations calculated dynamically from database"""
    query = db.query(PayableObligation)
    
    if payment_status:
        query = query.filter(PayableObligation.payment_status == payment_status)
    
    obligations = query.order_by(PayableObligation.created_at.desc()).offset(skip).limit(limit).all()
    
    return [
        {
            "id": obl.id,
            "invoice_id": obl.invoice_id,
            "invoice_number": obl.invoice.invoice_number if obl.invoice else None,
            "vendor": {
                "id": obl.vendor.id,
                "name": obl.vendor.name,
                "code": obl.vendor.vendor_code
            } if obl.vendor else None,
            "amount": obl.amount,
            "currency": obl.currency,
            "invoice_date": obl.invoice_date.isoformat() if obl.invoice_date else None,
            "due_date": obl.due_date.isoformat() if obl.due_date else None,
            "approval_status": obl.approval_status,
            "payment_status": obl.payment_status.value,
            "payment_reference": obl.payment_reference,
            "created_at": obl.created_at.isoformat(),
            "updated_at": obl.updated_at.isoformat() if obl.updated_at else None
        }
        for obl in obligations
    ]

@router.get("/{obligation_id}")
async def get_payable_obligation(obligation_id: int, db: Session = Depends(get_db)):
    """Get single payable obligation details"""
    obligation = db.query(PayableObligation).filter(PayableObligation.id == obligation_id).first()
    if not obligation:
        raise HTTPException(status_code=404, detail="Payable obligation not found")
    
    return {
        "id": obligation.id,
        "invoice_id": obligation.invoice_id,
        "invoice": {
            "id": obligation.invoice.id,
            "invoice_number": obligation.invoice.invoice_number,
            "status": obligation.invoice.status.value,
            "subtotal": obligation.invoice.subtotal,
            "tax_amount": obligation.invoice.tax_amount,
            "total_amount": obligation.invoice.total_amount
        } if obligation.invoice else None,
        "vendor": {
            "id": obligation.vendor.id,
            "name": obligation.vendor.name,
            "code": obligation.vendor.vendor_code,
            "email": obligation.vendor.email,
            "payment_terms": obligation.vendor.payment_terms
        } if obligation.vendor else None,
        "amount": obligation.amount,
        "currency": obligation.currency,
        "invoice_date": obligation.invoice_date.isoformat() if obligation.invoice_date else None,
        "due_date": obligation.due_date.isoformat() if obligation.due_date else None,
        "approval_status": obligation.approval_status,
        "payment_status": obligation.payment_status.value,
        "payment_reference": obligation.payment_reference,
        "created_at": obligation.created_at.isoformat(),
        "updated_at": obligation.updated_at.isoformat() if obligation.updated_at else None
    }

@router.post("/{obligation_id}/status")
async def update_payment_status(
    obligation_id: int,
    data: PaymentStatusUpdate,
    db: Session = Depends(get_db)
):
    """Update payment status (SCHEDULED, PAID, ON_HOLD, UNPAID) and audit"""
    obligation = db.query(PayableObligation).filter(PayableObligation.id == obligation_id).first()
    if not obligation:
        raise HTTPException(status_code=404, detail="Payable obligation not found")
    
    prev_status = obligation.payment_status.value
    obligation.payment_status = data.payment_status
    if data.payment_reference:
        obligation.payment_reference = data.payment_reference
    obligation.updated_at = datetime.utcnow()
    
    audit = AuditEvent(
        entity_type="PayableObligation",
        entity_id=obligation.id,
        action=AuditAction.PAYMENT_STATUS_CHANGED,
        actor_type=ActorType.USER,
        result=data.payment_status.value,
        event_metadata={
            "invoice_id": obligation.invoice_id,
            "previous_status": prev_status,
            "new_status": data.payment_status.value,
            "payment_reference": obligation.payment_reference,
            "note": data.note
        }
    )
    db.add(audit)
    db.commit()
    
    return {
        "status": "updated",
        "obligation_id": obligation.id,
        "payment_status": obligation.payment_status.value,
        "payment_reference": obligation.payment_reference
    }

@router.post("/{obligation_id}/pay")
async def record_payment(
    obligation_id: int,
    data: RecordPayment,
    db: Session = Depends(get_db)
):
    """Mark obligation as PAID with payment reference"""
    obligation = db.query(PayableObligation).filter(PayableObligation.id == obligation_id).first()
    if not obligation:
        raise HTTPException(status_code=404, detail="Payable obligation not found")
    
    prev_status = obligation.payment_status.value
    obligation.payment_status = PaymentStatus.PAID
    obligation.payment_reference = data.payment_reference
    obligation.updated_at = datetime.utcnow()
    
    # Also update invoice status
    if obligation.invoice:
        obligation.invoice.status = "PAID"
    
    audit = AuditEvent(
        entity_type="PayableObligation",
        entity_id=obligation.id,
        action=AuditAction.PAYMENT_STATUS_CHANGED,
        actor_type=ActorType.USER,
        result="PAID",
        event_metadata={
            "invoice_id": obligation.invoice_id,
            "previous_status": prev_status,
            "new_status": "PAID",
            "payment_reference": data.payment_reference,
            "amount": obligation.amount
        }
    )
    db.add(audit)
    db.commit()
    
    return {
        "status": "paid",
        "obligation_id": obligation.id,
        "payment_status": "PAID",
        "payment_reference": data.payment_reference
    }
