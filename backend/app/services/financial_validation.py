from typing import Dict, Any, List
from sqlalchemy.orm import Session
from ..models import Invoice, ControlStatus, ControlSeverity

class FinancialValidation:
    def __init__(self, db: Session):
        self.db = db
    
    async def validate_financials(self, invoice: Invoice) -> Dict[str, Any]:
        """Independently recalculate and validate invoice mathematics, tax, and terms"""
        errors: List[str] = []
        details: Dict[str, Any] = {}
        
        # 1. Currency validation
        if not invoice.currency or len(invoice.currency.strip()) < 3:
            errors.append(f"Invalid or missing currency code: '{invoice.currency}'")

        # 2. Line item math validation
        if invoice.items:
            calc_subtotal = 0.0
            calc_tax = 0.0
            line_errors = []

            for idx, item in enumerate(invoice.items, start=1):
                expected_line_total = round(item.quantity * item.unit_price, 2)
                if abs(expected_line_total - item.line_total) > 0.05:
                    line_errors.append(
                        f"Item #{idx} ({item.description}): Qty {item.quantity} × ${item.unit_price:.2f} = ${expected_line_total:.2f}, but line total is ${item.line_total:.2f}"
                    )
                calc_subtotal += item.line_total

                # Calculate item tax
                rate = item.tax_rate or 0.0
                if rate > 1.0:
                    rate = rate / 100.0  # normalize percentage e.g. 18% -> 0.18
                calc_tax += round(item.line_total * rate, 2)

            calc_subtotal = round(calc_subtotal, 2)
            calc_tax = round(calc_tax, 2)
            calc_total = round(calc_subtotal + calc_tax, 2)

            if line_errors:
                errors.extend(line_errors)

            # Subtotal consistency
            if abs(calc_subtotal - invoice.subtotal) > 0.05:
                errors.append(
                    f"Subtotal calculation mismatch: calculated sum of items is ${calc_subtotal:.2f}, but invoice states ${invoice.subtotal:.2f}"
                )

            # Tax amount consistency (if tax was specified)
            if invoice.tax_amount > 0 and abs(calc_tax - invoice.tax_amount) > 0.10:
                errors.append(
                    f"Tax calculation mismatch: calculated tax is ${calc_tax:.2f}, but invoice states ${invoice.tax_amount:.2f}"
                )

            # Total amount consistency
            if abs(calc_total - invoice.total_amount) > 0.05:
                errors.append(
                    f"Grand total mismatch: calculated total is ${calc_total:.2f}, but invoice states ${invoice.total_amount:.2f}"
                )

            details["calculated_subtotal"] = calc_subtotal
            details["calculated_tax"] = calc_tax
            details["calculated_total"] = calc_total
        else:
            # No line items: verify subtotal + tax = total
            expected_total = round((invoice.subtotal or 0.0) + (invoice.tax_amount or 0.0), 2)
            if abs(expected_total - invoice.total_amount) > 0.05:
                errors.append(
                    f"Header total mismatch: subtotal (${invoice.subtotal:.2f}) + tax (${invoice.tax_amount:.2f}) = ${expected_total:.2f}, but total is ${invoice.total_amount:.2f}"
                )
            details["calculated_total"] = expected_total

        # 3. Non-negative checks
        if invoice.total_amount <= 0:
            errors.append(f"Invoice total amount must be positive: ${invoice.total_amount:.2f}")

        # 4. Payment terms check
        if not invoice.payment_terms:
            details["terms_note"] = "Payment terms not specified (defaulting to standard Net 30)"

        details["stated_subtotal"] = invoice.subtotal
        details["stated_tax"] = invoice.tax_amount
        details["stated_total"] = invoice.total_amount

        if errors:
            return {
                "control": "FINANCIAL_VALIDATION",
                "status": ControlStatus.FAIL,
                "severity": ControlSeverity.CRITICAL if len(errors) > 1 else ControlSeverity.HIGH,
                "message": "; ".join(errors),
                "details": details
            }

        return {
            "control": "FINANCIAL_VALIDATION",
            "status": ControlStatus.PASS,
            "severity": ControlSeverity.NONE,
            "message": f"Mathematical integrity verified: subtotal ${invoice.subtotal:.2f} + tax ${invoice.tax_amount:.2f} = ${invoice.total_amount:.2f}",
            "details": details
        }
