"""
NOVA Dataset API
=================
Exposes dataset discovery, ingestion, and processing endpoints.

Architecture enforced here:
  NOVA API = DATA SOURCE ONLY
  PayGuard = INTELLIGENCE + CONTROLS + DECISIONS

Endpoints:
  GET  /api/nova/status        - Check NOVA connectivity + dataset summary
  POST /api/nova/discover      - Discover what datasets are available
  POST /api/nova/ingest        - Import NOVA dataset into PayGuard DB
  POST /api/nova/process       - Run PayGuard controls on all RECEIVED invoices
  POST /api/nova/ingest-and-process - Full pipeline (ingest → process)
  GET  /api/nova/summary       - Current ingestion state from DB
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    Invoice, InvoiceStatus, Vendor, PurchaseOrder, GoodsReceipt,
    AuditEvent, AuditAction, ActorType,
)
from ..services.nova_connector import NovaDatasetConnector
from ..services.dataset_ingestion import DatasetIngestionService
from ..services.control_engine import ControlEngine

logger = logging.getLogger("payguard.api.nova")
router = APIRouter(prefix="/api/nova", tags=["nova-dataset"])


@router.get("/status")
async def get_nova_status():
    """
    Check NOVA API connectivity and report available dataset sizes.
    Does not import any data.
    """
    connector = NovaDatasetConnector()
    result = await connector.check_connectivity()
    return result


@router.get("/summary")
async def get_ingestion_summary(db: Session = Depends(get_db)):
    """
    Return current state of imported NOVA data in PayGuard database.
    Shows what has already been ingested — no API call to NOVA.
    """
    total_vendors = db.query(Vendor).count()
    nova_vendors = db.query(Vendor).filter(Vendor.nova_vendor_id.isnot(None)).count()
    total_pos = db.query(PurchaseOrder).count()
    total_grns = db.query(GoodsReceipt).count()
    total_invoices = db.query(Invoice).count()

    status_counts: Dict[str, int] = {}
    for status in InvoiceStatus:
        count = db.query(Invoice).filter(Invoice.status == status).count()
        if count > 0:
            status_counts[status.value] = count

    # Last ingestion audit event
    last_ingest = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.entity_type == "NovaIngestion",
        )
        .order_by(AuditEvent.timestamp.desc())
        .first()
    )

    return {
        "payguard_database": {
            "vendors": {"total": total_vendors, "from_nova": nova_vendors},
            "purchase_orders": total_pos,
            "goods_receipts": total_grns,
            "invoices": {
                "total": total_invoices,
                "by_status": status_counts,
            },
        },
        "last_ingestion": {
            "timestamp": last_ingest.timestamp.isoformat() if last_ingest else None,
            "metadata": last_ingest.event_metadata if last_ingest else None,
        },
    }


@router.post("/ingest")
async def ingest_nova_dataset(db: Session = Depends(get_db)):
    """
    Import the NOVA pre-dataset into PayGuard's database.

    Pipeline:
      NOVA API → fetch vendors, POs, GRNs, invoices
        ↓ normalize
        ↓ upsert to PayGuard DB
        ↓ return ingestion summary

    Does NOT run PayGuard processing. Use /process or /ingest-and-process for that.
    """
    logger.info("Starting NOVA dataset ingestion via API request")

    ingestion_service = DatasetIngestionService(db)

    try:
        summary = await ingestion_service.run_full_ingestion()
    except Exception as e:
        logger.error(f"NOVA ingestion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

    # Record ingestion audit
    audit = AuditEvent(
        entity_type="NovaIngestion",
        entity_id=0,
        action=AuditAction.INVOICE_UPLOADED,
        actor_type=ActorType.SYSTEM,
        result="INGESTED",
        event_metadata=summary,
    )
    db.add(audit)
    db.commit()

    return summary


@router.post("/process")
async def process_ingested_invoices(
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """
    Run PayGuard's intelligence + control engine on all RECEIVED invoices.

    This is where PayGuard's own processing happens:
      - Entity resolution (vendor matching)
      - PO matching
      - Receipt verification
      - Duplicate detection
      - Financial + GST validation
      - Risk/anomaly scoring
      - Approval workflow

    NOVA is not involved in this step at all.
    """
    # Get unprocessed invoices (RECEIVED status)
    invoices_to_process = (
        db.query(Invoice)
        .filter(Invoice.status == InvoiceStatus.RECEIVED)
        .order_by(Invoice.invoice_date.asc())
        .limit(limit)
        .all()
    )

    if not invoices_to_process:
        return {
            "message": "No RECEIVED invoices to process",
            "processed": 0,
        }

    logger.info(f"Processing {len(invoices_to_process)} RECEIVED invoices through PayGuard controls")

    control_engine = ControlEngine(db)
    results = []
    errors = []

    for invoice in invoices_to_process:
        try:
            result = await control_engine.process_invoice(
                invoice=invoice,
                submitted_data={
                    "vendor_name": invoice.raw_vendor_name,
                    "tax_id": invoice.vendor_gstin,
                    "po_number": invoice.purchase_order.po_number if invoice.purchase_order else None,
                },
            )
            results.append({
                "invoice_id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "decision": result.get("decision"),
                "status": invoice.status.value,
            })
        except Exception as e:
            logger.error(f"Error processing invoice {invoice.id}: {e}", exc_info=True)
            errors.append({"invoice_id": invoice.id, "error": str(e)})

    return {
        "processed": len(results),
        "errors": len(errors),
        "results": results,
        "error_details": errors,
    }


@router.post("/ingest-and-process")
async def ingest_and_process(
    process_limit: int = 100,
    db: Session = Depends(get_db),
):
    """
    Full pipeline: import NOVA dataset → run PayGuard controls on imported invoices.

    Flow:
      NOVA API → ingestion → PayGuard DB → control engine → decisions
    """
    logger.info("Starting full NOVA ingest-and-process pipeline")

    # Step 1: Ingest
    ingestion_service = DatasetIngestionService(db)
    try:
        ingestion_summary = await ingestion_service.run_full_ingestion()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

    # Audit ingestion
    audit = AuditEvent(
        entity_type="NovaIngestion",
        entity_id=0,
        action=AuditAction.INVOICE_UPLOADED,
        actor_type=ActorType.SYSTEM,
        result="INGESTED",
        event_metadata=ingestion_summary,
    )
    db.add(audit)
    db.commit()

    # Step 2: Process newly ingested invoices
    new_invoice_ids = ingestion_summary["datasets"]["invoices"].get("invoice_ids", [])
    invoices_to_process = (
        db.query(Invoice)
        .filter(
            Invoice.id.in_(new_invoice_ids[:process_limit]),
            Invoice.status == InvoiceStatus.RECEIVED,
        )
        .all()
    )

    control_engine = ControlEngine(db)
    processed = []
    errors = []

    for invoice in invoices_to_process:
        try:
            result = await control_engine.process_invoice(
                invoice=invoice,
                submitted_data={
                    "vendor_name": invoice.raw_vendor_name,
                    "tax_id": invoice.vendor_gstin,
                    "po_number": invoice.purchase_order.po_number if invoice.purchase_order else None,
                },
            )
            processed.append({
                "invoice_id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "decision": result.get("decision"),
                "status": invoice.status.value,
            })
        except Exception as e:
            logger.error(f"Processing error for invoice {invoice.id}: {e}")
            errors.append({"invoice_id": invoice.id, "error": str(e)})

    return {
        "ingestion": ingestion_summary,
        "processing": {
            "attempted": len(invoices_to_process),
            "processed": len(processed),
            "errors": len(errors),
            "results": processed,
        },
    }
