from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

from ..database import get_db
from ..models import (
    Exception as InvoiceException, ExceptionStatus, Invoice, InvoiceStatus,
    AuditEvent, AuditAction, ActorType
)
from ..services import ApprovalEngine

router = APIRouter(prefix="/api/exceptions", tags=["exceptions"])

class ExceptionResolve(BaseModel):
    resolution: str = Field(..., min_length=3, description="Resolution description")
    notes: Optional[str] = None

class ExceptionOverride(BaseModel):
    override_reason: str = Field(..., min_length=5, description="Mandatory business reason for overriding the control failure")
    authorized_by: Optional[str] = "AP Supervisor"

class ExceptionReassign(BaseModel):
    assigned_to_name: str = Field(..., min_length=2)
    assigned_to_id: Optional[int] = None

class ExceptionReject(BaseModel):
    reason: str = Field(..., min_length=3)

@router.get("")
async def list_exceptions(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all exceptions with optional status and severity filtering"""
    query = db.query(InvoiceException)
    
    if status:
        query = query.filter(InvoiceException.status == status)
    if severity:
        query = query.filter(InvoiceException.severity == severity)
    
    exceptions = query.order_by(InvoiceException.created_at.desc()).offset(skip).limit(limit).all()
    
    return [
        {
            "id": exc.id,
            "invoice_id": exc.invoice_id,
            "invoice_number": exc.invoice.invoice_number if exc.invoice else None,
            "vendor_name": exc.invoice.vendor.name if (exc.invoice and exc.invoice.vendor) else (exc.invoice.raw_vendor_name if exc.invoice else "Unknown"),
            "amount": exc.invoice.total_amount if exc.invoice else 0.0,
            "currency": exc.invoice.currency if exc.invoice else "USD",
            "type": exc.type.value,
            "severity": exc.severity.value,
            "status": exc.status.value,
            "message": exc.message,
            "assigned_to_name": exc.assigned_to_name,
            "resolution": exc.resolution,
            "override_reason": exc.override_reason,
            "created_at": exc.created_at.isoformat(),
            "resolved_at": exc.resolved_at.isoformat() if exc.resolved_at else None
        }
        for exc in exceptions
    ]

@router.get("/{exception_id}")
async def get_exception(exception_id: int, db: Session = Depends(get_db)):
    """Get detailed information about a specific exception"""
    exc = db.query(InvoiceException).filter(InvoiceException.id == exception_id).first()
    if not exc:
        raise HTTPException(status_code=404, detail="Exception not found")
    
    return {
        "id": exc.id,
        "invoice_id": exc.invoice_id,
        "invoice": {
            "id": exc.invoice.id,
            "invoice_number": exc.invoice.invoice_number,
            "vendor_name": exc.invoice.vendor.name if exc.invoice.vendor else exc.invoice.raw_vendor_name,
            "amount": exc.invoice.total_amount,
            "status": exc.invoice.status.value
        } if exc.invoice else None,
        "type": exc.type.value,
        "severity": exc.severity.value,
        "status": exc.status.value,
        "message": exc.message,
        "resolution": exc.resolution,
        "resolution_notes": exc.resolution_notes,
        "override_reason": exc.override_reason,
        "assigned_to_name": exc.assigned_to_name,
        "created_at": exc.created_at.isoformat(),
        "resolved_at": exc.resolved_at.isoformat() if exc.resolved_at else None
    }

@router.post("/{exception_id}/resolve")
async def resolve_exception(
    exception_id: int,
    data: ExceptionResolve,
    db: Session = Depends(get_db)
):
    """Resolve an exception and evaluate if invoice can proceed to approval/payable"""
    exc = db.query(InvoiceException).filter(InvoiceException.id == exception_id).first()
    if not exc:
        raise HTTPException(status_code=404, detail="Exception not found")
    
    exc.status = ExceptionStatus.RESOLVED
    exc.resolution = data.resolution
    exc.resolution_notes = data.notes
    exc.resolved_at = datetime.utcnow()
    
    # Audit log
    audit = AuditEvent(
        entity_type="Exception",
        entity_id=exc.id,
        action=AuditAction.EXCEPTION_RESOLVED,
        actor_type=ActorType.USER,
        result="RESOLVED",
        event_metadata={
            "invoice_id": exc.invoice_id,
            "type": exc.type.value,
            "resolution": data.resolution,
            "notes": data.notes
        }
    )
    db.add(audit)
    db.commit()

    # Check if all exceptions on this invoice are now cleared
    await _check_and_progress_invoice(exc.invoice_id, db)
    return {"status": "resolved", "exception_id": exc.id, "invoice_id": exc.invoice_id}

@router.post("/{exception_id}/override")
async def override_exception(
    exception_id: int,
    data: ExceptionOverride,
    db: Session = Depends(get_db)
):
    """Override a control exception with mandatory business justification (audited without erasing control failure)"""
    exc = db.query(InvoiceException).filter(InvoiceException.id == exception_id).first()
    if not exc:
        raise HTTPException(status_code=404, detail="Exception not found")
    
    exc.status = ExceptionStatus.OVERRIDDEN
    exc.override_reason = data.override_reason
    exc.resolution = f"Overridden by {data.authorized_by}: {data.override_reason}"
    exc.resolved_at = datetime.utcnow()
    
    # Explicit audit event preserves the failure and records who overrode it
    audit = AuditEvent(
        entity_type="Exception",
        entity_id=exc.id,
        action=AuditAction.EXCEPTION_OVERRIDDEN,
        actor_type=ActorType.USER,
        result="OVERRIDDEN",
        event_metadata={
            "invoice_id": exc.invoice_id,
            "type": exc.type.value,
            "authorized_by": data.authorized_by,
            "override_reason": data.override_reason,
            "original_control_failure": exc.message
        }
    )
    db.add(audit)
    db.commit()

    # Check if remaining exceptions are resolved to progress invoice
    await _check_and_progress_invoice(exc.invoice_id, db)
    return {"status": "overridden", "exception_id": exc.id, "invoice_id": exc.invoice_id}

@router.post("/{exception_id}/reassign")
async def reassign_exception(
    exception_id: int,
    data: ExceptionReassign,
    db: Session = Depends(get_db)
):
    """Reassign exception to a designated reviewer or team"""
    exc = db.query(InvoiceException).filter(InvoiceException.id == exception_id).first()
    if not exc:
        raise HTTPException(status_code=404, detail="Exception not found")
    
    previous_assignee = exc.assigned_to_name
    exc.assigned_to_name = data.assigned_to_name
    exc.assigned_to = data.assigned_to_id
    exc.status = ExceptionStatus.IN_REVIEW

    audit = AuditEvent(
        entity_type="Exception",
        entity_id=exc.id,
        action=AuditAction.EXCEPTION_REASSIGNED,
        actor_type=ActorType.USER,
        result="REASSIGNED",
        event_metadata={
            "invoice_id": exc.invoice_id,
            "assigned_from": previous_assignee,
            "assigned_to": data.assigned_to_name
        }
    )
    db.add(audit)
    db.commit()
    return {"status": "reassigned", "exception_id": exc.id, "assigned_to": data.assigned_to_name}

@router.post("/{exception_id}/reject")
async def reject_exception(
    exception_id: int,
    data: ExceptionReject,
    db: Session = Depends(get_db)
):
    """Reject an invoice based on unresolved exception"""
    exc = db.query(InvoiceException).filter(InvoiceException.id == exception_id).first()
    if not exc:
        raise HTTPException(status_code=404, detail="Exception not found")
    
    exc.status = ExceptionStatus.REJECTED
    exc.resolution = f"Rejected: {data.reason}"
    exc.resolved_at = datetime.utcnow()
    
    invoice = exc.invoice
    if invoice:
        invoice.status = InvoiceStatus.REJECTED
    
    audit = AuditEvent(
        entity_type="Exception",
        entity_id=exc.id,
        action=AuditAction.REJECTED,
        actor_type=ActorType.USER,
        result="REJECTED",
        event_metadata={
            "invoice_id": exc.invoice_id,
            "reason": data.reason
        }
    )
    db.add(audit)
    db.commit()
    return {"status": "rejected", "exception_id": exc.id, "invoice_id": exc.invoice_id}

async def _check_and_progress_invoice(invoice_id: int, db: Session):
    """Check if all exceptions on this invoice are resolved/overridden, and route to approval/payable"""
    remaining_open = db.query(InvoiceException).filter(
        InvoiceException.invoice_id == invoice_id,
        InvoiceException.status.in_([ExceptionStatus.OPEN, ExceptionStatus.IN_REVIEW])
    ).count()

    if remaining_open == 0:
        invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if invoice and invoice.status not in (InvoiceStatus.REJECTED, InvoiceStatus.PAID):
            approval_engine = ApprovalEngine(db)
            approval_res = await approval_engine.determine_approval(invoice)

            if approval_res["requires_approval"]:
                invoice.status = InvoiceStatus.PENDING_REVIEW
                await approval_engine.create_approvals(invoice, approval_res["levels"])
            else:
                invoice.status = InvoiceStatus.APPROVED
                await approval_engine.create_payable_obligation(invoice)
            db.commit()
