"""
PayGuard Document Processor
=============================
Handles manually uploaded invoice documents (PDF, image, JSON, text).
Extracts structured invoice data using PayGuard's OWN parsing logic.

This is NOT NOVA. NOVA is a dataset source.
This handles documents manually uploaded by users through the UI.

Pipeline for uploaded documents:
  User uploads document
      ↓
  DocumentProcessor (this file) — local parsing
      ↓
  Normalized invoice dict
      ↓
  PayGuard DB
      ↓
  ControlEngine (PayGuard's intelligence layer)
"""

import os
import re
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("payguard.services.document_processor")

# Standard Indian GST rates
STANDARD_GST_RATES = {0, 5, 12, 18, 28}


class DocumentProcessor:
    """
    Processes manually uploaded invoice documents.
    Uses PayGuard's own parsing logic — does not call external AI APIs.
    """

    def parse_document(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Parse an uploaded invoice document and return normalized invoice data.
        Returns None if document cannot be parsed.
        """
        if not os.path.exists(file_path):
            logger.error(f"Document not found: {file_path}")
            return None

        ext = os.path.splitext(file_path)[1].lower()

        # Try PDF extraction
        if ext == ".pdf":
            text = self._extract_pdf_text(file_path)
        else:
            text = self._read_text_file(file_path)

        if not text or not text.strip():
            logger.warning(f"No text content found in {file_path}")
            return None

        # Try structured JSON first
        if ext == ".json" or text.strip().startswith("{"):
            try:
                data = json.loads(text)
                if isinstance(data, dict):
                    return self._normalize_json_invoice(data)
            except json.JSONDecodeError:
                pass

        # Fall back to heuristic text parsing
        return self._parse_text_invoice(text, file_path)

    def _extract_pdf_text(self, file_path: str) -> str:
        """Extract text from PDF using pypdf."""
        text = ""
        try:
            import pypdf
            reader = pypdf.PdfReader(file_path)
            for page in reader.pages:
                text += (page.extract_text() or "") + "\n"
        except ImportError:
            logger.warning("pypdf not installed — PDF parsing unavailable")
        except Exception as e:
            logger.warning(f"PDF extraction failed: {e}")
        return text

    def _read_text_file(self, file_path: str) -> str:
        """Read text/JSON file content."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception as e:
            logger.warning(f"Could not read file: {e}")
            return ""

    def _normalize_json_invoice(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalize a structured JSON invoice document."""
        vendor_data = data.get("vendor", {})
        if isinstance(vendor_data, str):
            vendor_data = {"name": vendor_data, "gstin": ""}

        subtotal = float(data.get("subtotal", 0.0) or 0.0)
        tax = float(data.get("tax_amount", 0.0) or data.get("gst_amount", 0.0) or 0.0)
        total = float(data.get("total_amount", 0.0) or (subtotal + tax))

        line_items = []
        for item in data.get("line_items", data.get("items", [])):
            try:
                qty = float(item.get("quantity", 1))
                price = float(item.get("unit_price", item.get("rate", 0)))
                gst_rate = float(item.get("gst_rate", item.get("tax_rate", 0)))
                taxable = float(item.get("amount", item.get("taxable_value", qty * price)))
                gst_amount = float(item.get("gst_amount", taxable * gst_rate / 100))
                line_total = float(item.get("line_total", taxable + gst_amount))
                line_items.append({
                    "description": str(item.get("description", "Item")),
                    "sku": str(item.get("sku", item.get("item_id", ""))),
                    "hsn_sac_code": item.get("hsn_code"),
                    "quantity": qty,
                    "unit_price": price,
                    "taxable_value": taxable,
                    "gst_rate": gst_rate,
                    "gst_amount": gst_amount,
                    "tax_rate": gst_rate / 100,
                    "line_total": line_total,
                })
            except (ValueError, TypeError):
                continue

        result = {
            "vendor": {
                "name": str(vendor_data.get("name", "")).strip(),
                "gstin": str(vendor_data.get("gstin", vendor_data.get("gst_number", ""))).strip(),
            },
            "invoice_number": str(data.get("invoice_number", "")).strip(),
            "invoice_date": data.get("invoice_date"),
            "due_date": data.get("due_date"),
            "po_number": str(data.get("po_number", "")).strip(),
            "currency": "INR",
            "place_of_supply": data.get("place_of_supply"),
            "subtotal": round(subtotal, 2),
            "tax_amount": round(tax, 2),
            "total_amount": round(total, 2),
            "line_items": line_items,
            "confidence": 0.95,
            "source": "UPLOADED_JSON",
        }

        return result if result["invoice_number"] or result["vendor"]["name"] else None

    def _parse_text_invoice(self, text: str, file_path: str) -> Dict[str, Any]:
        """Extract invoice fields from free-text using regex heuristics."""

        # Invoice number
        inv_match = re.search(
            r"(?:invoice\s*(?:no|number|#)?|inv\s*(?:no|#)?|bill\s*(?:no|#)?)\s*[:.]?\s*([A-Za-z0-9\-_/]+)",
            text, re.I,
        )
        invoice_number = inv_match.group(1).strip() if inv_match else f"INV-{os.path.basename(file_path)[:8].upper()}"

        # PO number
        po_match = re.search(
            r"(?:po\s*(?:no|number|#)?|purchase\s*order\s*(?:no|#)?)\s*[:.]?\s*([A-Za-z0-9\-_/]+)",
            text, re.I,
        )
        po_number = po_match.group(1).strip() if po_match else ""

        # GSTIN (15-char alphanumeric format)
        gstin_match = re.search(r"\b(\d{2}[A-Z]{5}\d{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})\b", text)
        gstin = gstin_match.group(1) if gstin_match else ""

        # Amounts (prefer INR amounts)
        total_match = re.search(
            r"(?:total\s*amount|grand\s*total|total)\s*[:.]?\s*(?:₹|Rs\.?|INR)?\s*([0-9,]+\.?[0-9]*)",
            text, re.I,
        )
        total_amount = float(total_match.group(1).replace(",", "")) if total_match else 0.0

        subtotal_match = re.search(
            r"(?:subtotal|taxable\s*value|sub\s*total)\s*[:.]?\s*(?:₹|Rs\.?|INR)?\s*([0-9,]+\.?[0-9]*)",
            text, re.I,
        )
        subtotal = float(subtotal_match.group(1).replace(",", "")) if subtotal_match else total_amount

        gst_match = re.search(
            r"(?:gst|igst|cgst|sgst|tax)\s*[:.]?\s*(?:₹|Rs\.?|INR)?\s*([0-9,]+\.?[0-9]*)",
            text, re.I,
        )
        tax_amount = float(gst_match.group(1).replace(",", "")) if gst_match else max(0.0, total_amount - subtotal)

        # Vendor name
        vendor_match = re.search(
            r"(?:vendor|supplier|from|bill\s*from|sold\s*by)\s*[:.]?\s*([^\n\r]{3,60})",
            text, re.I,
        )
        vendor_name = vendor_match.group(1).strip() if vendor_match else (text.strip().split("\n")[0].strip()[:60] or "Unknown Vendor")

        # Date
        date_match = re.search(
            r"(?:invoice\s*date|date)\s*[:.]?\s*(\d{4}-\d{2}-\d{2}|\d{2}[/-]\d{2}[/-]\d{4}|\d{2}-\d{2}-\d{4})",
            text, re.I,
        )
        invoice_date = date_match.group(1) if date_match else None

        return {
            "vendor": {
                "name": vendor_name,
                "gstin": gstin,
            },
            "invoice_number": invoice_number,
            "invoice_date": invoice_date,
            "due_date": None,
            "po_number": po_number,
            "currency": "INR",
            "subtotal": round(subtotal, 2),
            "tax_amount": round(tax_amount, 2),
            "total_amount": round(total_amount, 2) or round(subtotal + tax_amount, 2),
            "line_items": [
                {
                    "description": "Invoice Item",
                    "sku": "",
                    "quantity": 1.0,
                    "unit_price": round(subtotal, 2),
                    "taxable_value": round(subtotal, 2),
                    "gst_rate": round((tax_amount / subtotal * 100) if subtotal > 0 else 0.0, 2),
                    "gst_amount": round(tax_amount, 2),
                    "tax_rate": round(tax_amount / subtotal if subtotal > 0 else 0.0, 4),
                    "line_total": round(subtotal + tax_amount, 2),
                }
            ] if subtotal > 0 else [],
            "confidence": 0.65,
            "source": "UPLOADED_TEXT_PARSED",
        }
