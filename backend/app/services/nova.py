import os
import re
import logging
from typing import Dict, Any, Optional
import httpx
from ..config import get_settings

logger = logging.getLogger("payguard.services.nova")
settings = get_settings()

class NOVAService:
    def __init__(self):
        self.api_key = settings.nova_api_key
        self.api_url = settings.nova_api_url
    
    async def extract_invoice(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Extract invoice data from uploaded file using NOVA API with resilient parsing fallback"""
        if not os.path.exists(file_path):
            logger.error(f"Invoice file not found: {file_path}")
            return None
        
        extracted = None

        # 1. Attempt NOVA API extraction if configured
        if self.api_key and self.api_url:
            try:
                with open(file_path, "rb") as f:
                    file_content = f.read()
                
                async with httpx.AsyncClient(timeout=15.0) as client:
                    files = {"file": (os.path.basename(file_path), file_content)}
                    headers = {"Authorization": f"Bearer {self.api_key}"}
                    response = await client.post(
                        f"{self.api_url.rstrip('/')}/extract",
                        headers=headers,
                        files=files
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        normalized = self._normalize_extraction(data)
                        if self._validate_structure(normalized):
                            logger.info("NOVA extraction succeeded")
                            return normalized
                    else:
                        logger.warning(f"NOVA API returned status {response.status_code}")
            except Exception as e:
                logger.warning(f"NOVA API request failed: {str(e)}")

        # 2. Local Document Parser Fallback for PDF and Text files
        extracted = self._extract_from_local_document(file_path)
        if extracted and self._validate_structure(extracted):
            return extracted

        return None
    
    def _extract_from_local_document(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Extract invoice fields from PDF or text content using heuristics"""
        text = ""
        ext = os.path.splitext(file_path)[1].lower()

        if ext == ".pdf":
            try:
                import pypdf
                reader = pypdf.PdfReader(file_path)
                for page in reader.pages:
                    text += page.extract_text() or ""
            except Exception as e:
                logger.warning(f"Failed to read PDF text: {e}")
        else:
            # Check if text file or readable
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
            except Exception:
                text = ""

        if not text.strip():
            return None

        # Check if structured JSON electronic invoice
        try:
            import json
            json_data = json.loads(text)
            if isinstance(json_data, dict) and ("invoice_number" in json_data or "vendor" in json_data or "line_items" in json_data):
                normalized = self._normalize_extraction(json_data)
                if self._validate_structure(normalized):
                    return normalized
        except Exception:
            pass

        # Extract invoice number
        inv_match = re.search(r"(?:invoice\s*#?|inv\s*#?|bill\s*#?)\s*[:.]?\s*([A-Za-z0-9\-_]+)", text, re.I)
        invoice_number = inv_match.group(1) if inv_match else f"INV-{os.path.basename(file_path)[:8]}"

        # Extract PO number
        po_match = re.search(r"(?:po\s*#?|purchase\s*order\s*#?)\s*[:.]?\s*([A-Za-z0-9\-_]+)", text, re.I)
        po_number = po_match.group(1) if po_match else ""

        # Extract amounts
        total_match = re.search(r"(?:total\s*amount|total|grand\s*total)\s*[:.]?\s*[$₹€]?\s*([0-9,]+\.?[0-9]*)", text, re.I)
        total_amount = float(total_match.group(1).replace(",", "")) if total_match else 0.0

        subtotal_match = re.search(r"(?:subtotal|sub-total|sub\s*total)\s*[:.]?\s*[$₹€]?\s*([0-9,]+\.?[0-9]*)", text, re.I)
        subtotal = float(subtotal_match.group(1).replace(",", "")) if subtotal_match else total_amount

        tax_match = re.search(r"(?:tax|vat|gst)\s*[:.]?\s*[$₹€]?\s*([0-9,]+\.?[0-9]*)", text, re.I)
        tax_amount = float(tax_match.group(1).replace(",", "")) if tax_match else (total_amount - subtotal if total_amount >= subtotal else 0.0)

        # Extract vendor name (first non-empty line or keyword)
        vendor_match = re.search(r"(?:vendor|supplier|from)\s*[:.]?\s*([^\n\r]+)", text, re.I)
        vendor_name = vendor_match.group(1).strip() if vendor_match else text.strip().split("\n")[0].strip()[:50]
        if not vendor_name:
            vendor_name = "Unknown Vendor"

        # Extract date
        date_match = re.search(r"(?:date|invoice\s*date)\s*[:.]?\s*([0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{2}/[0-9]{2}/[0-9]{4})", text, re.I)
        invoice_date = date_match.group(1) if date_match else None

        return {
            "vendor": {
                "name": vendor_name,
                "tax_id": ""
            },
            "invoice_number": invoice_number,
            "invoice_date": invoice_date,
            "due_date": None,
            "po_number": po_number,
            "currency": "USD",
            "payment_terms": "Net 30",
            "subtotal": round(subtotal, 2),
            "tax_amount": round(tax_amount, 2),
            "total_amount": round(total_amount, 2),
            "line_items": [
                {
                    "description": "Standard Invoice Item",
                    "sku": "",
                    "quantity": 1.0,
                    "unit_price": round(subtotal, 2),
                    "tax_rate": round(tax_amount / subtotal, 4) if subtotal > 0 else 0.0,
                    "line_total": round(subtotal, 2)
                }
            ] if subtotal > 0 else [],
            "confidence": 0.75
        }

    def _normalize_extraction(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize API response to expected schema"""
        vendor_data = data.get("vendor", {})
        if isinstance(vendor_data, str):
            vendor_data = {"name": vendor_data, "tax_id": ""}

        line_items = []
        for item in data.get("line_items", []):
            try:
                qty = float(item.get("quantity", 1))
                price = float(item.get("unit_price", 0))
                rate = float(item.get("tax_rate", 0))
                total = float(item.get("line_total", qty * price))
                line_items.append({
                    "description": str(item.get("description", "Item")),
                    "sku": str(item.get("sku", "")),
                    "quantity": qty,
                    "unit_price": price,
                    "tax_rate": rate,
                    "line_total": total
                })
            except (ValueError, TypeError):
                continue

        subtotal = float(data.get("subtotal", 0.0) or 0.0)
        tax = float(data.get("tax_amount", 0.0) or 0.0)
        total = float(data.get("total_amount", 0.0) or (subtotal + tax))

        return {
            "vendor": {
                "name": str(vendor_data.get("name", "")).strip(),
                "tax_id": str(vendor_data.get("tax_id", "")).strip()
            },
            "invoice_number": str(data.get("invoice_number", "")).strip(),
            "invoice_date": data.get("invoice_date"),
            "due_date": data.get("due_date"),
            "po_number": str(data.get("po_number", "")).strip(),
            "currency": str(data.get("currency", "USD")),
            "payment_terms": str(data.get("payment_terms", "")),
            "subtotal": round(subtotal, 2),
            "tax_amount": round(tax, 2),
            "total_amount": round(total, 2),
            "line_items": line_items,
            "confidence": float(data.get("confidence", 0.85))
        }

    def _validate_structure(self, data: Optional[Dict[str, Any]]) -> bool:
        """Validate that extracted invoice has minimal required fields"""
        if not data:
            return False
        if not data.get("invoice_number"):
            return False
        if not data.get("vendor", {}).get("name"):
            return False
        return True
