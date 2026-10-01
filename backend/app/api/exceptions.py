from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from ..database import get_db
from ..models import Exception, ExceptionStatus, AuditEvent, AuditAction, ActorType
from pydantic import BaseModel

router = APIRouter(prefix="/api/exceptions", tags=["exceptions"])

class ExceptionResolve(BaseModel):
    resolution: str
    
class ExceptionReject(BaseModel):
    reason: str

@router.get("")
async def list_exceptions(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all exceptions"""
    query = db.query(Exception)
    
    if status:
        query = query.filter(Exception.status == status)
    
    exceptions = query.order_by(Exception.created_at.desc()).offset(skip).limit(limit).all()
    
    return [
        {
            "id": exc.id,
            "invoice_id": exc.invoice_id,
            "invoice_number": exc.invoice.invoice_number if exc.invoice else None,
            "vendor_name": exc.invoice.vendor.name if exc.invoice and exc.invoice.vendor else None,
            "type": exc.type.value,
            "severity": exc.severity.value,
            "status": exc.status.value,
            "message": exc.message,
            "created_at": exc.created_at.isoformat(),
            "resolved_at": exc.resolved_at.isoformat() if exc.resolved_at else None
        }
        for exc in exceptions
    ]

@router.get("/{exception_id}")
async def get_exception(exception_id: int, db: Session = Depends(get_db)):
    """Get exception details"""
    exception = db.query(Exception).filter(Exception.id == exception_id).first()
    
    if not exception:
        raise HTTPException(status_code=404, detail="Exception not found")
    
    return {
        "id": exception.id,
        "invoice_id": exception.invoice_id,
        "invoice": {
            "id": exception.invoice.id,
            "invoice_number": exception.invoice.invoice_number,
            "vendor_name": exception.invoice.vendor.name if exception.invoice.vendor else None,
            "amount": exception.invoice.total_amount
        } if exception.invoice else None,
        "type": exception.type.value,
        "severity": exception.severity.value,
        "status": exception.status.value,
        "message": exception.message,
        "resolution": exception.resolution,
        "assigned_to": exception.assigned_to,
        "created_at": exception.created_at.isoformat(),
        "resolved_at": exception.resolved_at.isoformat() if exception.resolved_at else None
    }

@router.post("/{exception_id}/resolve")
async def resolve_exception(
    exception_id: int,
    data: ExceptionResolve,
    db: Session = Depends(get_db)
):
    """Resolve an exception"""
    exception = db.query(Exception).filter(Exception.id == exception_id).first()
    
    if not exception:
        raise HTTPException(status_code=404, detail="Exception not found")
    
    exception.status = ExceptionStatus.RESOLVED
    exception.resolution = data.resolution
    exception.resolved_at = datetime.utcnow()
    
    # Create audit event
    audit = AuditEvent(
        entity_type="Exception",
        entity_id=exception.id,
        action=AuditAction.EXCEPTION_RESOLVED,
        actor_type=ActorType.USER,
        result="RESOLVED",
        metadata={"resolution": data.resolution}
    )
    db.add(audit)
    db.commit()
    
    return {"status": "resolved", "exception_id": exception.id}

@router.post("/{exception_id}/reject")
async def reject_exception(
    exception_id: int,
    data: ExceptionReject,
    db: Session = Depends(get_db)
):
    """Reject an exception"""
    exception = db.query(Exception).filter(Exception.id == exception_id).first()
    
    if not exception:
        raise HTTPException(status_code=404, detail="Exception not found")
    
    exception.status = ExceptionStatus.REJECTED
    exception.resolution = data.reason
    exception.resolved_at = datetime.utcnow()
    
    # Create audit event
    audit = AuditEvent(
        entity_type="Exception",
        entity_id=exception.id,
        action=AuditAction.REJECTED,
        actor_type=ActorType.USER,
        result="REJECTED",
        metadata={"reason": data.reason}
    )
    db.add(audit)
    db.commit()
    
    return {"status": "rejected", "exception_id": exception.id}
