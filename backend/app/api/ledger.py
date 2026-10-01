from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Optional

from ..database import get_db
from ..models import PayableObligation, PaymentStatus

router = APIRouter(prefix="/api/ledger", tags=["ledger"])

@router.get("")
async def list_payable_obligations(
    payment_status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all payable obligations"""
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
            "payment_status": obl.payment_status.value,
            "payment_reference": obl.payment_reference,
            "created_at": obl.created_at.isoformat()
        }
        for obl in obligations
    ]

@router.get("/{obligation_id}")
async def get_payable_obligation(obligation_id: int, db: Session = Depends(get_db)):
    """Get payable obligation details"""
    obligation = db.query(PayableObligation).filter(PayableObligation.id == obligation_id).first()
    
    if not obligation:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Payable obligation not found")
    
    return {
        "id": obligation.id,
        "invoice_id": obligation.invoice_id,
        "invoice": {
            "invoice_number": obligation.invoice.invoice_number,
            "status": obligation.invoice.status.value
        } if obligation.invoice else None,
        "vendor": {
            "id": obligation.vendor.id,
            "name": obligation.vendor.name,
            "code": obligation.vendor.vendor_code,
            "email": obligation.vendor.email
        } if obligation.vendor else None,
        "amount": obligation.amount,
        "currency": obligation.currency,
        "invoice_date": obligation.invoice_date.isoformat() if obligation.invoice_date else None,
        "due_date": obligation.due_date.isoformat() if obligation.due_date else None,
        "approval_status": obligation.approval_status,
        "payment_status": obligation.payment_status.value,
        "payment_reference": obligation.payment_reference,
        "created_at": obligation.created_at.isoformat(),
        "updated_at": obligation.updated_at.isoformat()
    }
