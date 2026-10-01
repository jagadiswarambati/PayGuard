from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from datetime import datetime
import os
import uuid

from ..database import get_db
from ..models import Invoice, InvoiceItem, Vendor, PurchaseOrder, InvoiceStatus, AuditEvent, AuditAction, ActorType
from ..services import NOVAService, ControlEngine
from ..config import get_settings

router = APIRouter(prefix="/api/invoices", tags=["invoices"])
settings = get_settings()

@router.post("/upload")
async def upload_invoice(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload and process invoice"""
    # Validate file type
    allowed_types = ["application/pdf", "image/png", "image/jpeg", "image/jpg"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF, PNG, JPG allowed.")
    
    # Save file
    file_id = str(uuid.uuid4())
    file_ext = os.path.splitext(file.filename)[1]
    file_path = os.path.join(settings.upload_dir, f"{file_id}{file_ext}")
    
    os.makedirs(settings.upload_dir, exist_ok=True)
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Extract data using NOVA
    nova_service = NOVAService()
    extracted_data = await nova_service.extract_invoice(file_path)
    
    if not extracted_data:
        # Create audit event for extraction failure
        audit = AuditEvent(
            entity_type="Invoice",
            entity_id=0,
            action=AuditAction.EXTRACTION_FAILED,
            actor_type=ActorType.SYSTEM,
            result="FAILED",
            metadata={"file": file.filename}
        )
        db.add(audit)
        db.commit()
        
        raise HTTPException(status_code=500, detail="Failed to extract invoice data")
    
    # Find or create vendor
    vendor = db.query(Vendor).filter(Vendor.name == extracted_data["vendor"]["name"]).first()
    if not vendor:
        vendor = Vendor(
            vendor_code=f"V{uuid.uuid4().hex[:8].upper()}",
            name=extracted_data["vendor"]["name"],
            tax_id=extracted_data["vendor"].get("tax_id")
        )
        db.add(vendor)
        db.flush()
    
    # Find PO if referenced
    po = None
    if extracted_data.get("po_number"):
        po = db.query(PurchaseOrder).filter(PurchaseOrder.po_number == extracted_data["po_number"]).first()
    
    # Create invoice
    invoice = Invoice(
        invoice_number=extracted_data["invoice_number"],
        vendor_id=vendor.id,
        po_id=po.id if po else None,
        invoice_date=datetime.fromisoformat(extracted_data["invoice_date"]) if extracted_data.get("invoice_date") else datetime.utcnow(),
        due_date=datetime.fromisoformat(extracted_data["due_date"]) if extracted_data.get("due_date") else None,
        currency=extracted_data.get("currency", "USD"),
        subtotal=extracted_data["subtotal"],
        tax_amount=extracted_data["tax_amount"],
        total_amount=extracted_data["total_amount"],
        payment_terms=extracted_data.get("payment_terms"),
        status=InvoiceStatus.RECEIVED,
        source_file=file_path,
        extraction_confidence=extracted_data.get("confidence", 0.0)
    )
    db.add(invoice)
    db.flush()
    
    # Create line items
    for item_data in extracted_data.get("line_items", []):
        item = InvoiceItem(
            invoice_id=invoice.id,
            description=item_data["description"],
            sku=item_data.get("sku"),
            quantity=item_data["quantity"],
            unit_price=item_data["unit_price"],
            tax_rate=item_data.get("tax_rate", 0.0),
            line_total=item_data["line_total"]
        )
        db.add(item)
    
    # Create audit event
    audit = AuditEvent(
        entity_type="Invoice",
        entity_id=invoice.id,
        action=AuditAction.INVOICE_UPLOADED,
        actor_type=ActorType.USER,
        result="SUCCESS",
        metadata={"file": file.filename, "vendor": vendor.name}
    )
    db.add(audit)
    db.commit()
    
    # Process invoice through control engine
    control_engine = ControlEngine(db)
    result = await control_engine.process_invoice(invoice)
    
    return {
        "invoice_id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "vendor": vendor.name,
        "total_amount": invoice.total_amount,
        "status": invoice.status.value,
        "control_result": result
    }

@router.get("")
async def list_invoices(
    skip: int = 0,
    limit: int = 100,
    status: str = None,
    db: Session = Depends(get_db)
):
    """List all invoices"""
    query = db.query(Invoice)
    
    if status:
        query = query.filter(Invoice.status == status)
    
    invoices = query.order_by(Invoice.created_at.desc()).offset(skip).limit(limit).all()
    
    return [
        {
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "vendor": {"id": inv.vendor.id, "name": inv.vendor.name} if inv.vendor else None,
            "total_amount": inv.total_amount,
            "currency": inv.currency,
            "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
            "due_date": inv.due_date.isoformat() if inv.due_date else None,
            "status": inv.status.value,
            "created_at": inv.created_at.isoformat()
        }
        for inv in invoices
    ]

@router.get("/{invoice_id}")
async def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    """Get invoice details"""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "vendor": {
            "id": invoice.vendor.id,
            "name": invoice.vendor.name,
            "code": invoice.vendor.vendor_code
        } if invoice.vendor else None,
        "purchase_order": {
            "id": invoice.purchase_order.id,
            "po_number": invoice.purchase_order.po_number
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
                "created_at": exc.created_at.isoformat()
            }
            for exc in invoice.exceptions
        ],
        "approvals": [
            {
                "id": app.id,
                "level": app.level.value,
                "status": app.status.value,
                "comment": app.comment,
                "approved_at": app.approved_at.isoformat() if app.approved_at else None
            }
            for app in invoice.approvals
        ],
        "created_at": invoice.created_at.isoformat(),
        "updated_at": invoice.updated_at.isoformat()
    }

@router.post("/{invoice_id}/process")
async def process_invoice(invoice_id: int, db: Session = Depends(get_db)):
    """Manually trigger invoice processing"""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    control_engine = ControlEngine(db)
    result = await control_engine.process_invoice(invoice)
    
    return result
