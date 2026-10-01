from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta

from ..database import get_db
from ..models import (
    Invoice, InvoiceStatus, Exception, ExceptionStatus,
    PayableObligation, PaymentStatus, AuditEvent
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

@router.get("")
async def get_dashboard(db: Session = Depends(get_db)):
    """Get dashboard metrics - ALL DYNAMICALLY CALCULATED"""
    
    # Invoice counts
    total_invoices = db.query(func.count(Invoice.id)).scalar() or 0
    pending_review = db.query(func.count(Invoice.id)).filter(
        Invoice.status == InvoiceStatus.PENDING_REVIEW
    ).scalar() or 0
    approved_invoices = db.query(func.count(Invoice.id)).filter(
        Invoice.status == InvoiceStatus.APPROVED
    ).scalar() or 0
    
    # Exception counts
    total_exceptions = db.query(func.count(Exception.id)).scalar() or 0
    open_exceptions = db.query(func.count(Exception.id)).filter(
        Exception.status == ExceptionStatus.OPEN
    ).scalar() or 0
    
    # Payable amounts
    payable_amount = db.query(func.sum(PayableObligation.amount)).filter(
        PayableObligation.payment_status == PaymentStatus.UNPAID
    ).scalar() or 0.0
    
    overdue_amount = db.query(func.sum(PayableObligation.amount)).filter(
        and_(
            PayableObligation.payment_status == PaymentStatus.UNPAID,
            PayableObligation.due_date < datetime.utcnow()
        )
    ).scalar() or 0.0
    
    paid_amount = db.query(func.sum(PayableObligation.amount)).filter(
        PayableObligation.payment_status == PaymentStatus.PAID
    ).scalar() or 0.0
    
    # Recent invoices
    recent_invoices = db.query(Invoice).order_by(
        Invoice.created_at.desc()
    ).limit(10).all()
    
    # Exception breakdown
    exception_breakdown = db.query(
        Exception.type,
        func.count(Exception.id).label('count')
    ).filter(
        Exception.status == ExceptionStatus.OPEN
    ).group_by(Exception.type).all()
    
    # Recent activity
    recent_activity = db.query(AuditEvent).order_by(
        AuditEvent.timestamp.desc()
    ).limit(20).all()
    
    # Invoice status distribution
    status_distribution = db.query(
        Invoice.status,
        func.count(Invoice.id).label('count')
    ).group_by(Invoice.status).all()
    
    return {
        "summary": {
            "total_invoices": total_invoices,
            "pending_review": pending_review,
            "approved": approved_invoices,
            "exceptions": open_exceptions,
            "payable_amount": round(payable_amount, 2),
            "overdue_amount": round(overdue_amount, 2),
            "paid_amount": round(paid_amount, 2)
        },
        "recent_invoices": [
            {
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "vendor_name": inv.vendor.name if inv.vendor else "Unknown",
                "amount": inv.total_amount,
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
                "status": status.value,
                "count": count
            }
            for status, count in status_distribution
        ],
        "recent_activity": [
            {
                "id": activity.id,
                "action": activity.action.value,
                "entity_type": activity.entity_type,
                "entity_id": activity.entity_id,
                "timestamp": activity.timestamp.isoformat(),
                "result": activity.result
            }
            for activity in recent_activity
        ]
    }
