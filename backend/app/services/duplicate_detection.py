from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_
from ..models import Invoice, InvoiceStatus, ControlStatus, ControlSeverity

class DuplicateDetection:
    def __init__(self, db: Session):
        self.db = db
    
    async def check_duplicate(self, invoice: Invoice) -> Dict[str, Any]:
        """Check for duplicate invoices"""
        
        # Check for exact duplicate: same vendor + invoice number
        exact_duplicate = self.db.query(Invoice).filter(
            and_(
                Invoice.vendor_id == invoice.vendor_id,
                Invoice.invoice_number == invoice.invoice_number,
                Invoice.id != invoice.id,
                Invoice.status.in_([InvoiceStatus.APPROVED, InvoiceStatus.PAID])
            )
        ).first()
        
        if exact_duplicate:
            return {
                "control": "DUPLICATE_CHECK",
                "status": ControlStatus.FAIL,
                "severity": ControlSeverity.CRITICAL,
                "message": f"Duplicate invoice found: {exact_duplicate.invoice_number}",
                "details": {
                    "duplicate_invoice_id": exact_duplicate.id,
                    "duplicate_invoice_number": exact_duplicate.invoice_number,
                    "duplicate_status": exact_duplicate.status.value,
                    "duplicate_amount": exact_duplicate.total_amount
                }
            }
        
        # Check for financial duplicate: same vendor + amount + date (within 7 days)
        from datetime import timedelta
        date_range_start = invoice.invoice_date - timedelta(days=7)
        date_range_end = invoice.invoice_date + timedelta(days=7)
        
        financial_duplicate = self.db.query(Invoice).filter(
            and_(
                Invoice.vendor_id == invoice.vendor_id,
                Invoice.total_amount == invoice.total_amount,
                Invoice.invoice_date >= date_range_start,
                Invoice.invoice_date <= date_range_end,
                Invoice.id != invoice.id,
                Invoice.status.in_([InvoiceStatus.APPROVED, InvoiceStatus.PAID])
            )
        ).first()
        
        if financial_duplicate:
            return {
                "control": "DUPLICATE_CHECK",
                "status": ControlStatus.WARNING,
                "severity": ControlSeverity.HIGH,
                "message": f"Possible duplicate: similar amount and date",
                "details": {
                    "possible_duplicate_id": financial_duplicate.id,
                    "possible_duplicate_number": financial_duplicate.invoice_number,
                    "amount": financial_duplicate.total_amount,
                    "date": str(financial_duplicate.invoice_date)
                }
            }
        
        return {
            "control": "DUPLICATE_CHECK",
            "status": ControlStatus.PASS,
            "severity": ControlSeverity.NONE,
            "message": "No duplicate invoice detected",
            "details": {}
        }
