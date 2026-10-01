import re
from datetime import timedelta
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from ..models import Invoice, ControlStatus, ControlSeverity

class DuplicateDetection:
    def __init__(self, db: Session):
        self.db = db
    
    def _normalize_invoice_num(self, num: str) -> str:
        """Strip non-alphanumeric characters and leading zeros for fuzzy match"""
        cleaned = re.sub(r"[^A-Za-z0-9]", "", num or "").upper()
        return cleaned.lstrip("0") or cleaned
    
    async def check_duplicate(self, invoice: Invoice) -> Dict[str, Any]:
        """Dynamically check for exact and suspicious duplicate invoices"""
        if not invoice.vendor_id or not invoice.invoice_number:
            return {
                "control": "DUPLICATE_CHECK",
                "status": ControlStatus.PASS,
                "severity": ControlSeverity.NONE,
                "message": "Insufficient data to run duplicate check",
                "details": {}
            }
        
        # 1. Exact match: same vendor + normalized invoice number
        all_vendor_invoices = self.db.query(Invoice).filter(
            Invoice.vendor_id == invoice.vendor_id,
            Invoice.id != (invoice.id or -1)
        ).all()
        
        curr_norm = self._normalize_invoice_num(invoice.invoice_number)
        
        for prior_inv in all_vendor_invoices:
            prior_norm = self._normalize_invoice_num(prior_inv.invoice_number)
            if prior_norm and (prior_norm == curr_norm or prior_inv.invoice_number.strip().lower() == invoice.invoice_number.strip().lower()):
                return {
                    "control": "DUPLICATE_CHECK",
                    "status": ControlStatus.FAIL,
                    "severity": ControlSeverity.CRITICAL,
                    "message": f"Exact duplicate invoice detected: invoice #{prior_inv.invoice_number} already exists for this vendor",
                    "details": {
                        "duplicate_invoice_id": prior_inv.id,
                        "duplicate_invoice_number": prior_inv.invoice_number,
                        "status": prior_inv.status.value,
                        "amount": prior_inv.total_amount,
                        "created_at": prior_inv.created_at.isoformat() if prior_inv.created_at else None
                    }
                }
        
        # 2. Duplicate against PO: same vendor + same PO + same amount
        if invoice.po_id:
            po_dup = self.db.query(Invoice).filter(
                and_(
                    Invoice.vendor_id == invoice.vendor_id,
                    Invoice.po_id == invoice.po_id,
                    Invoice.id != (invoice.id or -1),
                    Invoice.total_amount == invoice.total_amount
                )
            ).first()
            if po_dup:
                return {
                    "control": "DUPLICATE_CHECK",
                    "status": ControlStatus.FAIL,
                    "severity": ControlSeverity.HIGH,
                    "message": f"Duplicate billing suspected: invoice #{po_dup.invoice_number} already billed the exact same amount (${po_dup.total_amount:.2f}) against PO #{invoice.po_id}",
                    "details": {
                        "duplicate_invoice_id": po_dup.id,
                        "duplicate_invoice_number": po_dup.invoice_number,
                        "po_id": invoice.po_id,
                        "amount": po_dup.total_amount
                    }
                }
        
        # 3. Suspicious match: same vendor + same amount + invoice date within 14 days
        if invoice.invoice_date and invoice.total_amount:
            date_start = invoice.invoice_date - timedelta(days=14)
            date_end = invoice.invoice_date + timedelta(days=14)
            
            suspicious = self.db.query(Invoice).filter(
                and_(
                    Invoice.vendor_id == invoice.vendor_id,
                    Invoice.id != (invoice.id or -1),
                    Invoice.total_amount == invoice.total_amount,
                    Invoice.invoice_date >= date_start,
                    Invoice.invoice_date <= date_end
                )
            ).first()
            
            if suspicious:
                return {
                    "control": "DUPLICATE_CHECK",
                    "status": ControlStatus.WARNING,
                    "severity": ControlSeverity.HIGH,
                    "message": f"Suspicious duplicate: Invoice #{suspicious.invoice_number} has the exact same amount (${suspicious.total_amount:.2f}) within 14 days ({suspicious.invoice_date.strftime('%Y-%m-%d')})",
                    "details": {
                        "suspicious_invoice_id": suspicious.id,
                        "suspicious_invoice_number": suspicious.invoice_number,
                        "amount": suspicious.total_amount,
                        "date": suspicious.invoice_date.strftime('%Y-%m-%d')
                    }
                }
        
        return {
            "control": "DUPLICATE_CHECK",
            "status": ControlStatus.PASS,
            "severity": ControlSeverity.NONE,
            "message": "No duplicate invoices detected for this vendor and amount",
            "details": {}
        }
