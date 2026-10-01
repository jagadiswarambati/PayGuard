from typing import Dict, Any
from sqlalchemy.orm import Session
from ..models import Invoice, ControlStatus, ControlSeverity

class FinancialValidation:
    def __init__(self, db: Session):
        self.db = db
    
    async def validate_financials(self, invoice: Invoice) -> Dict[str, Any]:
        """Validate invoice financial calculations"""
        
        # Calculate expected values from line items
        if invoice.items:
            calculated_subtotal = sum(item.line_total for item in invoice.items)
            calculated_tax = sum(item.line_total * item.tax_rate for item in invoice.items)
            calculated_total = calculated_subtotal + calculated_tax
            
            # Check subtotal
            subtotal_diff = abs(calculated_subtotal - invoice.subtotal)
            if subtotal_diff > 0.01:  # Allow 1 cent rounding difference
                return {
                    "control": "FINANCIAL_VALIDATION",
                    "status": ControlStatus.FAIL,
                    "severity": ControlSeverity.HIGH,
                    "message": f"Subtotal mismatch: calculated {calculated_subtotal:.2f}, invoice shows {invoice.subtotal:.2f}",
                    "details": {
                        "calculated_subtotal": calculated_subtotal,
                        "invoice_subtotal": invoice.subtotal,
                        "difference": subtotal_diff
                    }
                }
            
            # Check tax
            tax_diff = abs(calculated_tax - invoice.tax_amount)
            if tax_diff > 0.01:
                return {
                    "control": "FINANCIAL_VALIDATION",
                    "status": ControlStatus.FAIL,
                    "severity": ControlSeverity.HIGH,
                    "message": f"Tax amount mismatch: calculated {calculated_tax:.2f}, invoice shows {invoice.tax_amount:.2f}",
                    "details": {
                        "calculated_tax": calculated_tax,
                        "invoice_tax": invoice.tax_amount,
                        "difference": tax_diff
                    }
                }
            
            # Check total
            total_diff = abs(calculated_total - invoice.total_amount)
            if total_diff > 0.01:
                return {
                    "control": "FINANCIAL_VALIDATION",
                    "status": ControlStatus.FAIL,
                    "severity": ControlSeverity.CRITICAL,
                    "message": f"Total amount mismatch: calculated {calculated_total:.2f}, invoice shows {invoice.total_amount:.2f}",
                    "details": {
                        "calculated_total": calculated_total,
                        "invoice_total": invoice.total_amount,
                        "difference": total_diff
                    }
                }
        
        # Verify line item calculations
        if invoice.items:
            for item in invoice.items:
                expected_line_total = item.quantity * item.unit_price
                line_diff = abs(expected_line_total - item.line_total)
                
                if line_diff > 0.01:
                    return {
                        "control": "FINANCIAL_VALIDATION",
                        "status": ControlStatus.FAIL,
                        "severity": ControlSeverity.HIGH,
                        "message": f"Line item calculation error for {item.description}",
                        "details": {
                            "item_description": item.description,
                            "quantity": item.quantity,
                            "unit_price": item.unit_price,
                            "expected_total": expected_line_total,
                            "actual_total": item.line_total
                        }
                    }
        
        return {
            "control": "FINANCIAL_VALIDATION",
            "status": ControlStatus.PASS,
            "severity": ControlSeverity.NONE,
            "message": "Financial validation passed",
            "details": {
                "subtotal": invoice.subtotal,
                "tax": invoice.tax_amount,
                "total": invoice.total_amount
            }
        }
