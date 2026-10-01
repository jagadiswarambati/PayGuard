"""
PayGuard Dataset Ingestion Pipeline
=====================================
Takes normalized NOVA data and persists it to the PayGuard database.

Flow:
  NOVA API → NovaDatasetConnector (fetch + normalize)
      ↓
  DatasetIngestionService (this file) — DB persistence
      ↓
  PayGuard Database (vendors, POs, GRNs, invoices)
      ↓
  ControlEngine (PayGuard's own intelligence layer)

NO AI processing happens here. This is purely ETL.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session

from ..models import (
    Vendor, VendorStatus,
    PurchaseOrder, PurchaseOrderItem, POStatus,
    GoodsReceipt, GoodsReceiptItem,
    Invoice, InvoiceItem, InvoiceStatus,
    AuditEvent, AuditAction, ActorType,
)
from .nova_connector import NovaDatasetConnector

logger = logging.getLogger("payguard.services.ingestion")


class DatasetIngestionService:
    """
    Ingests the NOVA pre-dataset into PayGuard's database.
    Handles deduplication (upsert by NOVA ID), referential integrity,
    and produces an ingestion summary for the API response.
    """

    def __init__(self, db: Session):
        self.db = db
        self.connector = NovaDatasetConnector()

    # ─── Vendor Ingestion ──────────────────────────────────────────────────

    def ingest_vendors(self, raw_vendors: List[Dict]) -> Dict[str, Any]:
        """Upsert vendor records. Returns {nova_id: db_id} map + stats."""
        created = updated = skipped = 0
        nova_id_to_db_id: Dict[str, int] = {}

        for raw in raw_vendors:
            normalized = self.connector.normalize_vendor(raw)
            nova_id = normalized["nova_vendor_id"]

            existing = (
                self.db.query(Vendor)
                .filter(Vendor.nova_vendor_id == nova_id)
                .first()
            )

            if existing:
                # Update mutable fields
                existing.name = normalized["name"]
                existing.gstin = normalized["gstin"]
                existing.pan = normalized["pan"]
                existing.email = normalized["email"]
                existing.phone = normalized["phone"]
                existing.address = normalized["address"]
                existing.state = normalized["state"]
                existing.state_code = normalized["state_code"]
                existing.category = normalized["category"]
                existing.status = VendorStatus(normalized["status"])
                existing.payment_terms = normalized["payment_terms"]
                existing.payment_terms_days = normalized["payment_terms_days"]
                existing.updated_at = datetime.utcnow()
                nova_id_to_db_id[nova_id] = existing.id
                updated += 1
            else:
                vendor = Vendor(
                    nova_vendor_id=nova_id,
                    vendor_code=normalized["vendor_code"],
                    name=normalized["name"],
                    gstin=normalized["gstin"],
                    pan=normalized["pan"],
                    email=normalized["email"],
                    phone=normalized["phone"],
                    address=normalized["address"],
                    state=normalized["state"],
                    state_code=normalized["state_code"],
                    bank_ifsc=normalized["bank_ifsc"],
                    bank_account_last4=normalized["bank_account_last4"],
                    category=normalized["category"],
                    status=VendorStatus(normalized["status"]),
                    payment_terms=normalized["payment_terms"],
                    payment_terms_days=normalized["payment_terms_days"],
                )
                self.db.add(vendor)
                self.db.flush()
                nova_id_to_db_id[nova_id] = vendor.id
                created += 1

        self.db.commit()
        logger.info(f"Vendors ingested: {created} created, {updated} updated")
        return {
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "nova_id_to_db_id": nova_id_to_db_id,
        }

    # ─── Name-based vendor lookup map ─────────────────────────────────────

    def build_name_to_vendor_id(self) -> Dict[str, int]:
        """Build a lowercase-name → db_id lookup for invoice vendor matching."""
        vendors = self.db.query(Vendor).all()
        return {v.name.lower(): v.id for v in vendors}

    # ─── Purchase Order Ingestion ──────────────────────────────────────────

    def ingest_purchase_orders(
        self, raw_pos: List[Dict], nova_vendor_id_to_db_id: Dict[str, int]
    ) -> Dict[str, Any]:
        """Upsert PO records. Returns {nova_po_id: db_po_id} map + stats."""
        created = updated = skipped = 0
        nova_po_id_to_db_id: Dict[str, int] = {}

        # Also build existing nova_po_id map from DB
        existing_pos = self.db.query(PurchaseOrder).all()
        existing_nova_ids = {}
        for po in existing_pos:
            # Store using po_number as key since we don't have nova_po_id column yet
            if hasattr(po, 'nova_po_id') and po.nova_po_id:
                existing_nova_ids[po.nova_po_id] = po

        for raw in raw_pos:
            normalized = self.connector.normalize_purchase_order(
                raw, nova_vendor_id_to_db_id
            )
            if normalized is None:
                skipped += 1
                continue

            nova_po_id = normalized["nova_po_id"]
            po_number = normalized["po_number"]

            # Check by po_number (unique) since nova_po_id may not be stored yet
            existing = (
                self.db.query(PurchaseOrder)
                .filter(PurchaseOrder.po_number == po_number)
                .first()
            )

            if existing:
                existing.total_amount = normalized["total_amount"]
                existing.status = POStatus(normalized["status"])
                existing.updated_at = datetime.utcnow()
                nova_po_id_to_db_id[nova_po_id] = existing.id
                updated += 1
            else:
                po = PurchaseOrder(
                    po_number=po_number,
                    vendor_id=normalized["vendor_id"],
                    po_date=normalized["po_date"],
                    currency=normalized["currency"],
                    status=POStatus(normalized["status"]),
                    total_amount=normalized["total_amount"],
                )
                self.db.add(po)
                self.db.flush()

                for item_data in normalized["items"]:
                    po_item = PurchaseOrderItem(
                        purchase_order_id=po.id,
                        description=item_data["description"],
                        sku=item_data["sku"],
                        quantity=item_data["quantity"],
                        unit_price=item_data["unit_price"],
                        tax_rate=item_data["tax_rate"],
                        line_total=item_data["line_total"],
                    )
                    self.db.add(po_item)

                nova_po_id_to_db_id[nova_po_id] = po.id
                created += 1

        self.db.commit()
        logger.info(f"POs ingested: {created} created, {updated} updated, {skipped} skipped")
        return {
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "nova_po_id_to_db_id": nova_po_id_to_db_id,
        }

    # ─── Goods Receipt Ingestion ───────────────────────────────────────────

    def ingest_goods_receipts(
        self, raw_grns: List[Dict], nova_po_id_to_db_id: Dict[str, int]
    ) -> Dict[str, Any]:
        """Upsert GRN records."""
        created = updated = skipped = 0

        for raw in raw_grns:
            normalized = self.connector.normalize_goods_receipt(
                raw, nova_po_id_to_db_id
            )
            if normalized is None:
                skipped += 1
                continue

            grn_number = normalized["grn_number"]
            existing = (
                self.db.query(GoodsReceipt)
                .filter(GoodsReceipt.receipt_number == grn_number)
                .first()
            )

            if existing:
                updated += 1
                continue

            # Get PO items for this PO to try to link GRN items
            from ..models import PurchaseOrderItem
            po_id = normalized["po_id"]
            po_items = (
                self.db.query(PurchaseOrderItem)
                .filter(PurchaseOrderItem.purchase_order_id == po_id)
                .all()
            )
            # Build item_id → po_item_id map
            item_id_map = {pi.sku: pi.id for pi in po_items if pi.sku}

            grn = GoodsReceipt(
                receipt_number=grn_number,
                purchase_order_id=po_id,
                received_date=normalized["received_date"],
                status="RECEIVED",
            )
            self.db.add(grn)
            self.db.flush()

            for grn_item in normalized["items"]:
                item_id = grn_item.get("item_id", "")
                po_item_id = item_id_map.get(item_id)

                # If we can't match by item_id, use first PO item
                if not po_item_id and po_items:
                    po_item_id = po_items[0].id

                if po_item_id:
                    grn_item_obj = GoodsReceiptItem(
                        goods_receipt_id=grn.id,
                        po_item_id=po_item_id,
                        quantity_received=grn_item["qty_received"],
                    )
                    self.db.add(grn_item_obj)

            created += 1

        self.db.commit()
        logger.info(f"GRNs ingested: {created} created, {updated} updated, {skipped} skipped")
        return {"created": created, "updated": updated, "skipped": skipped}

    # ─── Invoice Ingestion ─────────────────────────────────────────────────

    def ingest_invoices(
        self,
        raw_invoices: List[Dict],
        name_to_vendor_id: Dict[str, int],
    ) -> Dict[str, Any]:
        """
        Upsert invoice records from NOVA dataset into PayGuard DB.
        Sets status to RECEIVED — PayGuard's control engine processes them separately.
        """
        created = updated = skipped = 0
        invoice_ids: List[int] = []

        for raw in raw_invoices:
            normalized = self.connector.normalize_invoice(raw, name_to_vendor_id)

            if not normalized.get("invoice_number"):
                skipped += 1
                continue

            invoice_number = normalized["invoice_number"]
            nova_invoice_id = normalized.get("nova_invoice_id")

            # Deduplicate by invoice_number
            existing = (
                self.db.query(Invoice)
                .filter(Invoice.invoice_number == invoice_number)
                .first()
            )

            if existing:
                # Update amount fields in case dataset changed
                existing.total_amount = normalized["total_amount"]
                existing.subtotal = normalized["subtotal"]
                existing.tax_amount = normalized["tax_amount"]
                existing.cgst_amount = normalized["cgst_amount"]
                existing.sgst_amount = normalized["sgst_amount"]
                existing.igst_amount = normalized["igst_amount"]
                existing.vendor_id = normalized["vendor_id"] or existing.vendor_id
                existing.nova_invoice_id = nova_invoice_id
                existing.updated_at = datetime.utcnow()
                invoice_ids.append(existing.id)
                updated += 1
            else:
                invoice = Invoice(
                    invoice_number=invoice_number,
                    nova_invoice_id=nova_invoice_id,
                    vendor_id=normalized["vendor_id"],
                    raw_vendor_name=normalized["raw_vendor_name"],
                    vendor_gstin=normalized.get("vendor_gstin"),
                    invoice_date=normalized["invoice_date"],
                    due_date=normalized.get("due_date"),
                    currency=normalized.get("currency", "INR"),
                    subtotal=normalized["subtotal"],
                    cgst_amount=normalized["cgst_amount"],
                    sgst_amount=normalized["sgst_amount"],
                    igst_amount=normalized["igst_amount"],
                    tax_amount=normalized["tax_amount"],
                    total_amount=normalized["total_amount"],
                    intra_state=normalized.get("intra_state", False),
                    discount_amount=normalized.get("discount_amount", 0.0),
                    status=InvoiceStatus.RECEIVED,
                    extraction_confidence=1.0,  # structured data, full confidence
                )
                self.db.add(invoice)
                self.db.flush()

                for item_data in normalized.get("items", []):
                    inv_item = InvoiceItem(
                        invoice_id=invoice.id,
                        description=item_data["description"],
                        sku=item_data.get("sku") or "",
                        hsn_sac_code=item_data.get("hsn_sac_code"),
                        quantity=item_data["quantity"],
                        unit_price=item_data["unit_price"],
                        taxable_value=item_data.get("taxable_value", 0.0),
                        gst_rate=item_data.get("gst_rate", 0.0),
                        gst_amount=item_data.get("gst_amount", 0.0),
                        cgst_rate=item_data.get("cgst_rate", 0.0),
                        sgst_rate=item_data.get("sgst_rate", 0.0),
                        igst_rate=item_data.get("igst_rate", 0.0),
                        tax_rate=item_data.get("tax_rate", 0.0),
                        line_total=item_data["line_total"],
                        discount=item_data.get("discount", 0.0),
                    )
                    self.db.add(inv_item)

                # Audit: dataset record ingested
                audit = AuditEvent(
                    entity_type="Invoice",
                    entity_id=invoice.id,
                    action=AuditAction.INVOICE_UPLOADED,
                    actor_type=ActorType.SYSTEM,
                    result="INGESTED",
                    event_metadata={
                        "source": "NOVA_DATASET",
                        "nova_invoice_id": nova_invoice_id,
                        "invoice_number": invoice_number,
                        "vendor": normalized["raw_vendor_name"],
                        "total_amount": normalized["total_amount"],
                        "currency": "INR",
                    },
                )
                self.db.add(audit)
                invoice_ids.append(invoice.id)
                created += 1

        self.db.commit()
        logger.info(f"Invoices ingested: {created} created, {updated} updated, {skipped} skipped")
        return {
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "invoice_ids": invoice_ids,
        }

    # ─── Full Ingestion Orchestrator ───────────────────────────────────────

    async def run_full_ingestion(self) -> Dict[str, Any]:
        """
        Run the complete NOVA dataset ingestion pipeline:
        1. Fetch all datasets from NOVA API
        2. Persist in correct order (vendors → POs → GRNs → invoices)
        3. Return ingestion summary
        
        Does NOT run PayGuard processing. Caller must trigger ControlEngine separately.
        """
        logger.info("Starting NOVA full dataset ingestion")
        started_at = datetime.utcnow()

        # Step 1: Fetch all datasets
        logger.info("Fetching NOVA datasets...")
        raw_vendors = await self.connector.fetch_vendors()
        raw_pos = await self.connector.fetch_purchase_orders()
        raw_grns = await self.connector.fetch_goods_receipts()
        raw_invoices = await self.connector.fetch_invoices()

        logger.info(
            f"Fetched: {len(raw_vendors)} vendors, {len(raw_pos)} POs, "
            f"{len(raw_grns)} GRNs, {len(raw_invoices)} invoices"
        )

        # Step 2: Ingest vendors first (other records depend on vendor IDs)
        vendor_result = self.ingest_vendors(raw_vendors)
        nova_vendor_id_to_db_id = vendor_result["nova_id_to_db_id"]

        # Step 3: Ingest POs (depend on vendors)
        po_result = self.ingest_purchase_orders(raw_pos, nova_vendor_id_to_db_id)
        nova_po_id_to_db_id = po_result["nova_po_id_to_db_id"]

        # Step 4: Ingest GRNs (depend on POs)
        grn_result = self.ingest_goods_receipts(raw_grns, nova_po_id_to_db_id)

        # Step 5: Ingest invoices (name-match to vendors)
        name_to_vendor_id = self.build_name_to_vendor_id()
        invoice_result = self.ingest_invoices(raw_invoices, name_to_vendor_id)

        elapsed = (datetime.utcnow() - started_at).total_seconds()

        summary = {
            "status": "completed",
            "source": "NOVA_API",
            "ingested_at": started_at.isoformat(),
            "elapsed_seconds": round(elapsed, 2),
            "datasets": {
                "vendors": {
                    "fetched": len(raw_vendors),
                    "created": vendor_result["created"],
                    "updated": vendor_result["updated"],
                },
                "purchase_orders": {
                    "fetched": len(raw_pos),
                    "created": po_result["created"],
                    "updated": po_result["updated"],
                    "skipped": po_result["skipped"],
                },
                "goods_receipts": {
                    "fetched": len(raw_grns),
                    "created": grn_result["created"],
                    "updated": grn_result["updated"],
                    "skipped": grn_result["skipped"],
                },
                "invoices": {
                    "fetched": len(raw_invoices),
                    "created": invoice_result["created"],
                    "updated": invoice_result["updated"],
                    "skipped": invoice_result["skipped"],
                    "invoice_ids": invoice_result["invoice_ids"],
                },
            },
        }

        logger.info(f"NOVA ingestion complete in {elapsed:.1f}s: {summary['datasets']}")
        return summary
