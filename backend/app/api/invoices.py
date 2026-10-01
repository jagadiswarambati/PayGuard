from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Dict, Any, Optional
from datetime import datetime
import os
import uuid

from ..database import get_db
from ..models import (
    Invoice, InvoiceItem, Vendor, PurchaseOrder, InvoiceStatus,
    AuditEvent, AuditAction, ActorType,
    Exception as InvoiceException, ExceptionType, ExceptionSeverity, ExceptionStatus
)
from ..services import NOVAService, ControlEngine
from ..config import get_settings

router = APIRouter(prefix="/api/invoices", tags=["invoices"])
settings = get_settings()

@router.post("/upload")
async def upload_invoice(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload and process invoice with secure NOVA extraction and deterministic controls"""
    allowed_types = ["application/pdf", "image/png", "image/jpeg", "image/jpg", "text/plain", "application/json"]
    if file.content_type not in allowed_types and not file.filename.lower().endswith((".pdf", ".png", ".jpg", ".jpeg", ".json", ".txt")):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '{file.content_type}'. Supported: PDF, PNG, JPG, JSON, TXT."
        )
    
    # Save file
    file_id = str(uuid.uuid4())
    file_ext = os.path.splitext(file.filename)[1].lower() or ".pdf"
    file_path = os.path.join(settings.upload_dir, f"{file_id}{file_ext}")
    
    os.makedirs(settings.upload_dir, exist_ok=True)
    
    content = await file.read()
    if len(content) > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds maximum upload limit of {settings.max_upload_size_mb} MB"
        )

    with open(file_path, "wb") as f:
        f.write(content)
    
    # Create initial audit log
    audit_upload = AuditEvent(
        entity_type="Document",
        entity_id=0,
        action=AuditAction.INVOICE_UPLOADED,
        actor_type=ActorType.USER,
        result="UPLOADED",
        event_metadata={"filename": file.filename, "file_path": file_path, "size_bytes": len(content)}
    )
    db.add(audit_upload)
    db.commit()

    # Extract invoice using NOVA
    nova_service = NOVAService()
    extracted_data = await nova_service.extract_invoice(file_path)

    if not extracted_data:
        # Graceful handling: Create invoice in PENDING_REVIEW with EXTRACTION_FAILED exception
        fallback_inv_num = f"INV-{uuid.uuid4().hex[:8].upper()}"
        invoice = Invoice(
            invoice_number=fallback_inv_num,
            vendor_id=None,
            raw_vendor_name="Unknown Vendor",
            po_id=None,
            invoice_date=datetime.utcnow(),
            due_date=None,
            currency="USD",
            subtotal=0.0,
            tax_amount=0.0,
            total_amount=0.0,
            status=InvoiceStatus.PENDING_REVIEW,
            source_file=file_path,
            extraction_confidence=0.0
        )
        db.add(invoice)
        db.flush()

        exc = InvoiceException(
            invoice_id=invoice.id,
            type=ExceptionType.EXTRACTION_FAILED,
            severity=ExceptionSeverity.CRITICAL,
            status=ExceptionStatus.OPEN,
            message=f"Automated document extraction failed for {file.filename}. Manual review and data entry required."
        )
        db.add(exc)

        audit_fail = AuditEvent(
            entity_type="Invoice",
            entity_id=invoice.id,
            action=AuditAction.EXTRACTION_FAILED,
            actor_type=ActorType.SYSTEM,
            result="EXTRACTION_FAILED",
            event_metadata={"filename": file.filename, "reason": "Unreadable document format or extraction error"}
        )
        db.add(audit_fail)
        db.commit()

        return {
            "invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "vendor": "Unknown",
            "total_amount": 0.0,
            "status": invoice.status.value,
            "control_result": {
                "decision": "EXCEPTION",
                "decision_reason": "Extraction failed: manual review required",
                "controls": [],
                "exceptions": [{"type": "EXTRACTION_FAILED", "message": exc.message}]
            }
        }

    # Match Vendor in Database
    extracted_vendor_name = extracted_data.get("vendor", {}).get("name", "").strip()
    extracted_tax_id = extracted_data.get("vendor", {}).get("tax_id", "").strip()
    
    vendor = None
    if extracted_vendor_name:
        vendor = db.query(Vendor).filter(Vendor.name.ilike(extracted_vendor_name)).first()
    if not vendor and extracted_tax_id:
        vendor = db.query(Vendor).filter(Vendor.tax_id == extracted_tax_id).first()

    # Match PO in Database
    po = None
    extracted_po_num = extracted_data.get("po_number", "").strip()
    if extracted_po_num:
        po = db.query(PurchaseOrder).filter(PurchaseOrder.po_number.ilike(extracted_po_num)).first()

    # Dates
    inv_date = datetime.utcnow()
    if extracted_data.get("invoice_date"):
        try:
            inv_date = datetime.fromisoformat(extracted_data["invoice_date"].replace("Z", ""))
        except Exception:
            inv_date = datetime.utcnow()

    due_date = None
    if extracted_data.get("due_date"):
        try:
            due_date = datetime.fromisoformat(extracted_data["due_date"].replace("Z", ""))
        except Exception:
            pass

    invoice = Invoice(
        invoice_number=extracted_data["invoice_number"],
        vendor_id=vendor.id if vendor else None,
        raw_vendor_name=extracted_vendor_name or "Unknown Vendor",
        po_id=po.id if po else None,
        invoice_date=inv_date,
        due_date=due_date,
        currency=extracted_data.get("currency", "USD"),
        subtotal=extracted_data.get("subtotal", 0.0),
        tax_amount=extracted_data.get("tax_amount", 0.0),
        total_amount=extracted_data.get("total_amount", 0.0),
        payment_terms=extracted_data.get("payment_terms", "Net 30"),
        status=InvoiceStatus.RECEIVED,
        source_file=file_path,
        extraction_confidence=extracted_data.get("confidence", 0.85)
    )
    db.add(invoice)
    db.flush()

    # Add line items
    for item_data in extracted_data.get("line_items", []):
        db.add(InvoiceItem(
            invoice_id=invoice.id,
            description=item_data.get("description", "Item"),
            sku=item_data.get("sku"),
            quantity=item_data.get("quantity", 1.0),
            unit_price=item_data.get("unit_price", 0.0),
            tax_rate=item_data.get("tax_rate", 0.0),
            line_total=item_data.get("line_total", 0.0)
        ))
    
    # Audit log
    audit_extracted = AuditEvent(
        entity_type="Invoice",
        entity_id=invoice.id,
        action=AuditAction.EXTRACTION_COMPLETED,
        actor_type=ActorType.SYSTEM,
        result="SUCCESS",
        event_metadata={
            "invoice_number": invoice.invoice_number,
            "vendor": extracted_vendor_name,
            "confidence": invoice.extraction_confidence
        }
    )
    db.add(audit_extracted)
    db.commit()

    # Run Control Engine
    control_engine = ControlEngine(db)
    result = await control_engine.process_invoice(
        invoice=invoice,
        submitted_data={
            "vendor_name": extracted_vendor_name,
            "tax_id": extracted_tax_id,
            "po_number": extracted_po_num
        }
    )

    return {
        "invoice_id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "vendor": vendor.name if vendor else (extracted_vendor_name or "Unknown"),
        "total_amount": invoice.total_amount,
        "status": invoice.status.value,
        "control_result": result
    }

@router.get("")
async def list_invoices(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List invoices with search and status filtering"""
    query = db.query(Invoice)
    
    if status:
        query = query.filter(Invoice.status == status)
    
    if search:
        term = f"%{search.strip()}%"
        query = query.outerjoin(Vendor).filter(
            or_(
                Invoice.invoice_number.ilike(term),
                Invoice.raw_vendor_name.ilike(term),
                Vendor.name.ilike(term)
            )
        )
    
    invoices = query.order_by(Invoice.created_at.desc()).offset(skip).limit(limit).all()
    
    return [
        {
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "vendor": {
                "id": inv.vendor.id,
                "name": inv.vendor.name,
                "code": inv.vendor.vendor_code
            } if inv.vendor else {"id": None, "name": inv.raw_vendor_name or "Unknown", "code": None},
            "purchase_order": {
                "id": inv.purchase_order.id,
                "po_number": inv.purchase_order.po_number
            } if inv.purchase_order else None,
            "total_amount": inv.total_amount,
            "currency": inv.currency,
            "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
            "due_date": inv.due_date.isoformat() if inv.due_date else None,
            "status": inv.status.value,
            "extraction_confidence": inv.extraction_confidence,
            "created_at": inv.created_at.isoformat()
        }
        for inv in invoices
    ]

@router.get("/{invoice_id}")
async def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    """Get complete invoice details including controls, exceptions, approvals, payable, and audit trail"""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Fetch audit events for this invoice
    audit_events = db.query(AuditEvent).filter(
        or_(
            (AuditEvent.entity_type == "Invoice") & (AuditEvent.entity_id == invoice.id),
            (AuditEvent.entity_type == "PayableObligation") & (AuditEvent.entity_id == invoice.id)
        )
    ).order_by(AuditEvent.timestamp.desc()).all()

    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "vendor": {
            "id": invoice.vendor.id,
            "name": invoice.vendor.name,
            "code": invoice.vendor.vendor_code,
            "status": invoice.vendor.status.value,
            "tax_id": invoice.vendor.tax_id
        } if invoice.vendor else {"id": None, "name": invoice.raw_vendor_name or "Unknown", "code": None, "status": "UNREGISTERED", "tax_id": None},
        "purchase_order": {
            "id": invoice.purchase_order.id,
            "po_number": invoice.purchase_order.po_number,
            "total_amount": invoice.purchase_order.total_amount,
            "status": invoice.purchase_order.status.value
        } if invoice.purchase_order else None,
        "invoice_date": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
        "currency": invoice.currency,
        "subtotal": invoice.subtotal,
        "tax_amount": invoice.tax_amount,
        "total_amount": invoice.total_amount,
        "payment_terms": invoice.payment_terms,
        "status": invoice.status.value,
        "extraction_confidence": invoice.extraction_confidence,
        "items": [
            {
                "id": item.id,
                "description": item.description,
                "sku": item.sku,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "tax_rate": item.tax_rate,
                "line_total": item.line_total
            }
            for item in invoice.items
        ],
        "control_results": [
            {
                "id": cr.id,
                "control_name": cr.control_name,
                "status": cr.status.value,
                "severity": cr.severity.value,
                "message": cr.message,
                "details": cr.details,
                "created_at": cr.created_at.isoformat()
            }
            for cr in invoice.control_results
        ],
        "exceptions": [
            {
                "id": exc.id,
                "type": exc.type.value,
                "severity": exc.severity.value,
                "status": exc.status.value,
                "message": exc.message,
                "resolution": exc.resolution,
                "override_reason": exc.override_reason,
                "assigned_to_name": exc.assigned_to_name,
                "created_at": exc.created_at.isoformat(),
                "resolved_at": exc.resolved_at.isoformat() if exc.resolved_at else None
            }
            for exc in invoice.exceptions
        ],
        "approvals": [
            {
                "id": app.id,
                "level": app.level.value,
                "status": app.status.value,
                "comment": app.comment,
                "approved_at": app.approved_at.isoformat() if app.approved_at else None,
                "created_at": app.created_at.isoformat()
            }
            for app in invoice.approvals
        ],
        "payable_obligation": {
            "id": invoice.payable_obligation.id,
            "amount": invoice.payable_obligation.amount,
            "currency": invoice.payable_obligation.currency,
            "payment_status": invoice.payable_obligation.payment_status.value,
            "payment_reference": invoice.payable_obligation.payment_reference,
            "due_date": invoice.payable_obligation.due_date.isoformat() if invoice.payable_obligation.due_date else None,
            "created_at": invoice.payable_obligation.created_at.isoformat()
        } if invoice.payable_obligation else None,
        "audit_events": [
            {
                "id": event.id,
                "action": event.action.value,
                "actor_type": event.actor_type.value,
                "result": event.result,
                "metadata": event.event_metadata or {},
                "timestamp": event.timestamp.isoformat()
            }
            for event in audit_events
        ],
        "created_at": invoice.created_at.isoformat(),
        "updated_at": invoice.updated_at.isoformat()
    }

@router.post("/{invoice_id}/process")
async def process_invoice(invoice_id: int, db: Session = Depends(get_db)):
    """Manually re-run control engine on an invoice"""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    control_engine = ControlEngine(db)
    result = await control_engine.process_invoice(invoice)
    return result
