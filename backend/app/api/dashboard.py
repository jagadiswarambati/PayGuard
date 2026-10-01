from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime

from ..database import get_db
from ..models import (
    Invoice, InvoiceStatus, Exception as InvoiceException, ExceptionStatus,
    Approval, ApprovalStatus,
    PayableObligation, PaymentStatus, AuditEvent
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

@router.get("")
async def get_dashboard(db: Session = Depends(get_db)):
    """Get dashboard metrics - 100% dynamically calculated from actual database records"""
    
    # 1. Invoice counts
    total_invoices = db.query(func.count(Invoice.id)).scalar() or 0
    pending_review = db.query(func.count(Invoice.id)).filter(
        Invoice.status == InvoiceStatus.PENDING_REVIEW
    ).scalar() or 0
    approved_invoices = db.query(func.count(Invoice.id)).filter(
        Invoice.status.in_([InvoiceStatus.APPROVED, InvoiceStatus.PAID])
    ).scalar() or 0
    rejected_invoices = db.query(func.count(Invoice.id)).filter(
        Invoice.status == InvoiceStatus.REJECTED
    ).scalar() or 0
    on_hold_invoices = db.query(func.count(Invoice.id)).filter(
        Invoice.status == InvoiceStatus.ON_HOLD
    ).scalar() or 0
    
    # 2. Exception counts
    total_exceptions = db.query(func.count(InvoiceException.id)).scalar() or 0
    open_exceptions = db.query(func.count(InvoiceException.id)).filter(
        InvoiceException.status.in_([ExceptionStatus.OPEN, ExceptionStatus.IN_REVIEW])
    ).scalar() or 0
    
    # 3. Pending approvals
    pending_approvals = db.query(func.count(Approval.id)).filter(
        Approval.status == ApprovalStatus.PENDING
    ).scalar() or 0
    
    # 4. Payable amounts
    payable_amount = db.query(func.sum(PayableObligation.amount)).filter(
        PayableObligation.payment_status.in_([PaymentStatus.UNPAID, PaymentStatus.SCHEDULED])
    ).scalar() or 0.0
    
    now = datetime.utcnow()
    overdue_amount = db.query(func.sum(PayableObligation.amount)).filter(
        and_(
            PayableObligation.payment_status == PaymentStatus.UNPAID,
            PayableObligation.due_date != None,
            PayableObligation.due_date < now
        )
    ).scalar() or 0.0
    
    paid_amount = db.query(func.sum(PayableObligation.amount)).filter(
        PayableObligation.payment_status == PaymentStatus.PAID
    ).scalar() or 0.0
    
    # 5. Recent invoices
    recent_invoices = db.query(Invoice).order_by(
        Invoice.created_at.desc()
    ).limit(8).all()
    
    # 6. Exception breakdown by type
    exception_breakdown = db.query(
        InvoiceException.type,
        func.count(InvoiceException.id).label('count')
    ).filter(
        InvoiceException.status.in_([ExceptionStatus.OPEN, ExceptionStatus.IN_REVIEW])
    ).group_by(InvoiceException.type).all()
    
    # 7. Recent activity
    recent_activity = db.query(AuditEvent).order_by(
        AuditEvent.timestamp.desc()
    ).limit(15).all()
    
    # 8. Invoice status distribution
    status_distribution = db.query(
        Invoice.status,
        func.count(Invoice.id).label('count')
    ).group_by(Invoice.status).all()
    
    return {
        "summary": {
            "total_invoices": total_invoices,
            "pending_review": pending_review,
            "approved": approved_invoices,
            "rejected": rejected_invoices,
            "on_hold": on_hold_invoices,
            "exceptions": open_exceptions,
            "total_exceptions": total_exceptions,
            "pending_approvals": pending_approvals,
            "payable_amount": round(float(payable_amount), 2),
            "overdue_amount": round(float(overdue_amount), 2),
            "paid_amount": round(float(paid_amount), 2)
        },
        "recent_invoices": [
            {
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "vendor_name": inv.vendor.name if inv.vendor else (inv.raw_vendor_name or "Unknown"),
                "amount": inv.total_amount,
                "currency": inv.currency,
                "status": inv.status.value,
                "created_at": inv.created_at.isoformat()
            }
            for inv in recent_invoices
        ],
        "exception_breakdown": [
            {
                "type": exc_type.value,
                "count": count
            }
            for exc_type, count in exception_breakdown
        ],
        "status_distribution": [
            {
                "status": st.value,
                "count": count
            }
            for st, count in status_distribution
        ],
        "recent_activity": [
            {
                "id": act.id,
                "action": act.action.value,
                "entity_type": act.entity_type,
                "entity_id": act.entity_id,
                "result": act.result,
                "metadata": act.event_metadata or {},
                "timestamp": act.timestamp.isoformat()
            }
            for act in recent_activity
        ]
    }
