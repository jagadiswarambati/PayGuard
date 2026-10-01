"""
NOVA Dataset Ingestion Service
================================
Connects to the NOVA API as a DATA SOURCE ONLY.
Downloads datasets: vendors, purchase orders, goods receipts, and invoices.
Normalizes and inserts them into PayGuard's database.

NOVA API = External Pre-Dataset Source
PayGuard = Intelligence + Controls + Decisions
"""

import logging
import asyncio
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, date
from sqlalchemy.orm import Session
import httpx

from ..config import get_settings

logger = logging.getLogger("payguard.services.nova_ingestion")
settings = get_settings()

# ─── NOVA API Dataset Summary (discovered) ─────────────────────────────────
# /vendors        → 21 vendor records  (GST, PAN, bank details, state)
# /purchase-orders→ 175 PO records     (vendor_id, items, amounts)
# /goods-receipts → 174 GRN records    (po_id, items received)
# /invoices       → 300 invoice records (client_name, GST breakdown, items)
# /payments       → 303 payment records (linked to invoices)
# ─────────────────────────────────────────────────────────────────────────────

NOVA_STATUS_MAP = {
    "active": "ACTIVE",
    "inactive": "INACTIVE",
    "blocked": "BLOCKED",
}

PO_STATUS_MAP = {
    "open": "OPEN",
    "partial": "PARTIALLY_RECEIVED",
    "received": "RECEIVED",
    "closed": "CLOSED",
    "cancelled": "CANCELLED",
}


class NovaDatasetConnector:
    """
    Connector for the NOVA external dataset API.
    Responsible ONLY for data retrieval, pagination, and normalization.
    No AI processing, no approval decisions, no validation logic.
    """

    def __init__(self):
        self.api_key = settings.nova_api_key
        self.base_url = settings.nova_api_url.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

    async def _fetch_paginated(
        self, endpoint: str, limit: int = 200
    ) -> List[Dict[str, Any]]:
        """Fetch all pages from a paginated NOVA endpoint."""
        all_records: List[Dict[str, Any]] = []
        offset = 0

        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                url = f"{self.base_url}/{endpoint}?limit={limit}&offset={offset}"
                try:
                    resp = await client.get(url, headers=self._get_headers())
                    resp.raise_for_status()
                    data = resp.json()
                except httpx.HTTPStatusError as e:
                    logger.error(
                        f"NOVA API HTTP error {e.response.status_code} for {endpoint}: {e}"
                    )
                    break
                except Exception as e:
                    logger.error(f"NOVA API request failed for {endpoint}: {e}")
                    break

                records = data.get("data", [])
                all_records.extend(records)

                pagination = data.get("pagination", {})
                has_more = pagination.get("has_more", False)
                if not has_more or not records:
                    break
                offset += limit

        logger.info(f"NOVA API: fetched {len(all_records)} records from /{endpoint}")
        return all_records

    # ─── Dataset Retrieval Methods ──────────────────────────────────────────

    async def fetch_vendors(self) -> List[Dict[str, Any]]:
        """Retrieve all vendor records from NOVA dataset."""
        return await self._fetch_paginated("vendors")

    async def fetch_purchase_orders(self) -> List[Dict[str, Any]]:
        """Retrieve all purchase order records from NOVA dataset."""
        return await self._fetch_paginated("purchase-orders")

    async def fetch_goods_receipts(self) -> List[Dict[str, Any]]:
        """Retrieve all goods receipt records from NOVA dataset."""
        return await self._fetch_paginated("goods-receipts")

    async def fetch_invoices(self) -> List[Dict[str, Any]]:
        """Retrieve all invoice records from NOVA dataset."""
        return await self._fetch_paginated("invoices")

    async def check_connectivity(self) -> Dict[str, Any]:
        """Check connectivity to NOVA API and return dataset summary."""
        if not self.api_key:
            return {"connected": False, "error": "API key not configured"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/health", headers=self._get_headers()
                )
                if resp.status_code != 200:
                    return {"connected": False, "error": f"HTTP {resp.status_code}"}

            # Get dataset sizes (first page only for quick check)
            counts = {}
            for endpoint in ["vendors", "purchase-orders", "goods-receipts", "invoices"]:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    r = await client.get(
                        f"{self.base_url}/{endpoint}?limit=1",
                        headers=self._get_headers(),
                    )
                    if r.status_code == 200:
                        d = r.json()
                        counts[endpoint] = d.get("pagination", {}).get("total", 0)
                    else:
                        counts[endpoint] = None

            return {
                "connected": True,
                "base_url": self.base_url,
                "datasets": {
                    "vendors": counts.get("vendors"),
                    "purchase_orders": counts.get("purchase-orders"),
                    "goods_receipts": counts.get("goods-receipts"),
                    "invoices": counts.get("invoices"),
                },
            }

        except Exception as e:
            return {"connected": False, "error": str(e)}

    # ─── Normalization Methods ─────────────────────────────────────────────
    # These convert NOVA's schema to PayGuard's internal normalized structure.
    # No business logic is applied here — that is PayGuard's job.

    def normalize_vendor(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a NOVA vendor record to PayGuard vendor schema."""
        name = (raw.get("name") or "").strip()
        vendor_code = f"VEN-NOVA-{raw['id'][-6:].upper()}"

        state = raw.get("state") or ""
        state_code = raw.get("state_code") or ""

        return {
            "nova_vendor_id": raw.get("id"),
            "vendor_code": vendor_code,
            "name": name,
            "gstin": raw.get("gst_number") or None,
            "pan": raw.get("pan") or None,
            "email": raw.get("email") or None,
            "phone": raw.get("phone") or None,
            "address": raw.get("address") or None,
            "state": state,
            "state_code": state_code,
            "bank_ifsc": raw.get("bank_ifsc") or None,
            "bank_account_last4": raw.get("bank_account_last4") or None,
            "category": raw.get("category") or None,
            "status": NOVA_STATUS_MAP.get(
                (raw.get("status") or "active").lower(), "ACTIVE"
            ),
            "payment_terms": f"Net {raw.get('payment_terms_days', 30)}",
            "payment_terms_days": int(raw.get("payment_terms_days") or 30),
        }

    def normalize_purchase_order(
        self, raw: Dict[str, Any], nova_vendor_id_to_db_id: Dict[str, int]
    ) -> Optional[Dict[str, Any]]:
        """Normalize a NOVA PO record to PayGuard PO schema."""
        nova_vendor_id = raw.get("vendor_id")
        db_vendor_id = nova_vendor_id_to_db_id.get(nova_vendor_id)

        if not db_vendor_id:
            logger.warning(
                f"PO {raw.get('po_number')}: vendor {nova_vendor_id} not found in DB — skipping"
            )
            return None

        order_date = self._parse_date(raw.get("order_date")) or datetime.utcnow()
        total_amount = float(raw.get("total_amount") or 0.0)
        status = PO_STATUS_MAP.get((raw.get("status") or "open").lower(), "OPEN")

        items = []
        for item in raw.get("items", []):
            qty = float(item.get("qty") or 1.0)
            unit_price = float(item.get("unit_price") or 0.0)
            gst_rate = float(item.get("gst_rate") or 0.0)
            taxable = round(qty * unit_price, 2)
            gst_amount = round(taxable * gst_rate / 100, 2)
            line_total = round(taxable + gst_amount, 2)
            items.append({
                "sku": item.get("item_id") or "",
                "description": item.get("description") or "Item",
                "quantity": qty,
                "unit_price": unit_price,
                "tax_rate": gst_rate / 100,
                "line_total": line_total,
            })

        return {
            "nova_po_id": raw.get("id"),
            "po_number": raw.get("po_number"),
            "vendor_id": db_vendor_id,
            "po_date": order_date,
            "currency": "INR",
            "status": status,
            "total_amount": total_amount,
            "items": items,
        }

    def normalize_goods_receipt(
        self, raw: Dict[str, Any], nova_po_id_to_db_id: Dict[str, int]
    ) -> Optional[Dict[str, Any]]:
        """Normalize a NOVA GRN record to PayGuard GoodsReceipt schema."""
        nova_po_id = raw.get("po_id")
        db_po_id = nova_po_id_to_db_id.get(nova_po_id)

        if not db_po_id:
            logger.warning(
                f"GRN {raw.get('grn_number')}: PO {nova_po_id} not found in DB — skipping"
            )
            return None

        received_date = self._parse_date(raw.get("received_date")) or datetime.utcnow()

        items = []
        for item in raw.get("items", []):
            qty_received = float(item.get("qty_received") or 0.0)
            items.append({
                "item_id": item.get("item_id") or "",
                "qty_received": qty_received,
                "qty_rejected": float(item.get("qty_rejected") or 0.0),
            })

        return {
            "nova_grn_id": raw.get("id"),
            "grn_number": raw.get("grn_number"),
            "po_id": db_po_id,
            "nova_po_id": nova_po_id,
            "received_date": received_date,
            "items": items,
        }

    def normalize_invoice(
        self,
        raw: Dict[str, Any],
        name_to_vendor_id: Dict[str, int],
    ) -> Dict[str, Any]:
        """
        Normalize a NOVA invoice record to PayGuard invoice schema.
        
        Note: NOVA invoices use client_name (vendor name from buyer perspective).
        PayGuard matches client_name against vendor master to resolve vendor_id.
        """
        invoice_number = raw.get("invoice_number") or ""
        client_name = (raw.get("client_name") or "").strip()
        client_gstin = raw.get("client_gst_number") or None

        # Attempt vendor resolution by name (case-insensitive)
        vendor_id = name_to_vendor_id.get(client_name.lower())

        invoice_date = self._parse_date(raw.get("invoice_date")) or datetime.utcnow()
        due_date = self._parse_date(raw.get("due_date"))

        subtotal = float(raw.get("amount") or 0.0)
        gst_amount = float(raw.get("gst_amount") or 0.0)
        cgst_amount = float(raw.get("cgst_amount") or 0.0)
        sgst_amount = float(raw.get("sgst_amount") or 0.0)
        igst_amount = float(raw.get("igst_amount") or 0.0)
        total_amount = float(raw.get("total_amount") or subtotal + gst_amount)
        intra_state = bool(raw.get("intra_state", False))

        items = []
        for item in raw.get("items", []):
            qty = float(item.get("quantity") or 1.0)
            unit_price = float(item.get("rate") or 0.0)
            gst_rate_pct = float(item.get("gst_rate") or 0.0)
            taxable_value = float(item.get("amount") or qty * unit_price)
            item_gst = float(item.get("gst_amount") or taxable_value * gst_rate_pct / 100)
            line_total = round(taxable_value + item_gst, 2)

            items.append({
                "description": item.get("description") or "Item",
                "sku": item.get("item_id") or "",
                "hsn_sac_code": item.get("hsn_code") or None,
                "quantity": qty,
                "unit_price": unit_price,
                "taxable_value": taxable_value,
                "gst_rate": gst_rate_pct,
                "gst_amount": item_gst,
                "cgst_rate": gst_rate_pct / 2 if intra_state else 0.0,
                "sgst_rate": gst_rate_pct / 2 if intra_state else 0.0,
                "igst_rate": gst_rate_pct if not intra_state else 0.0,
                "tax_rate": gst_rate_pct / 100,
                "line_total": line_total,
                "discount": float(item.get("discount") or 0.0),
            })

        return {
            "nova_invoice_id": raw.get("id"),
            "invoice_number": invoice_number,
            "vendor_id": vendor_id,
            "raw_vendor_name": client_name,
            "vendor_gstin": client_gstin,
            "invoice_date": invoice_date,
            "due_date": due_date,
            "currency": raw.get("currency") or "INR",
            "subtotal": round(subtotal, 2),
            "cgst_amount": round(cgst_amount, 2),
            "sgst_amount": round(sgst_amount, 2),
            "igst_amount": round(igst_amount, 2),
            "tax_amount": round(gst_amount, 2),
            "total_amount": round(total_amount, 2),
            "intra_state": intra_state,
            "discount_amount": float(raw.get("discount_amount") or 0.0),
            "items": items,
            "nova_status": raw.get("status") or "pending",
        }

    def _parse_date(self, val: Optional[str]) -> Optional[datetime]:
        if not val:
            return None
        try:
            if "T" in str(val):
                return datetime.fromisoformat(str(val).replace("Z", "+00:00").replace("+00:00", ""))
            return datetime.strptime(str(val)[:10], "%Y-%m-%d")
        except Exception:
            return None
