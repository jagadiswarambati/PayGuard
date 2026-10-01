import re
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from ..models import Invoice, PurchaseOrder, POStatus, ControlStatus, ControlSeverity
from .settings_service import get_all_settings

class POMatching:
    def __init__(self, db: Session):
        self.db = db
    
    def _get_tolerances(self):
        settings = get_all_settings(self.db)
        return (
            float(settings.get("po_price_tolerance", 0.05)),
            float(settings.get("po_quantity_tolerance", 0.05))
        )
    
    async def match_po(self, invoice: Invoice, submitted_po_number: str = None) -> Dict[str, Any]:
        """Match invoice against purchase order with configurable tolerances"""
        price_tolerance, qty_tolerance = self._get_tolerances()

        po = None
        if invoice.po_id:
            po = self.db.query(PurchaseOrder).filter(PurchaseOrder.id == invoice.po_id).first()
        elif submitted_po_number:
            po = self.db.query(PurchaseOrder).filter(PurchaseOrder.po_number == submitted_po_number.strip()).first()
            if po and not invoice.po_id:
                invoice.po_id = po.id
                self.db.flush()

        if not po:
            if submitted_po_number:
                return {
                    "control": "PO_MATCH",
                    "status": ControlStatus.FAIL,
                    "severity": ControlSeverity.CRITICAL,
                    "message": f"Purchase order '{submitted_po_number}' was not found in the system",
                    "details": {"submitted_po_number": submitted_po_number}
                }
            return {
                "control": "PO_MATCH",
                "status": ControlStatus.WARNING,
                "severity": ControlSeverity.MEDIUM,
                "message": "No purchase order reference provided on invoice",
                "details": {}
            }
        
        # Check PO status
        if po.status in (POStatus.CANCELLED, POStatus.CLOSED):
            return {
                "control": "PO_MATCH",
                "status": ControlStatus.FAIL,
                "severity": ControlSeverity.CRITICAL,
                "message": f"Purchase order {po.po_number} is {po.status.value}",
                "details": {"po_number": po.po_number, "status": po.status.value}
            }
        
        # Verify vendor matches
        if invoice.vendor_id and po.vendor_id != invoice.vendor_id:
            return {
                "control": "PO_MATCH",
                "status": ControlStatus.FAIL,
                "severity": ControlSeverity.CRITICAL,
                "message": f"Invoice vendor does not match PO vendor for {po.po_number}",
                "details": {
                    "po_number": po.po_number,
                    "invoice_vendor_id": invoice.vendor_id,
                    "po_vendor_id": po.vendor_id
                }
            }
        
        # Check total amount tolerance
        amount_diff = abs(invoice.total_amount - po.total_amount)
        allowed_amount_tolerance = round(po.total_amount * price_tolerance, 2)
        
        if amount_diff > allowed_amount_tolerance:
            return {
                "control": "PO_MATCH",
                "status": ControlStatus.FAIL,
                "severity": ControlSeverity.HIGH,
                "message": f"Invoice total (${invoice.total_amount:.2f}) exceeds PO total (${po.total_amount:.2f}) beyond ±{price_tolerance*100:.0f}% tolerance (${allowed_amount_tolerance:.2f})",
                "details": {
                    "po_number": po.po_number,
                    "invoice_amount": invoice.total_amount,
                    "po_amount": po.total_amount,
                    "difference": round(amount_diff, 2),
                    "allowed_tolerance": allowed_amount_tolerance
                }
            }
        
        # Match line items
        mismatches: List[Dict[str, Any]] = []
        if invoice.items and po.items:
            for inv_item in invoice.items:
                matched_po_item = None

                # Match by SKU first
                if inv_item.sku:
                    for p_item in po.items:
                        if p_item.sku and p_item.sku.strip().lower() == inv_item.sku.strip().lower():
                            matched_po_item = p_item
                            break
                
                # Match by description keywords
                if not matched_po_item and inv_item.description:
                    inv_words = set(re.findall(r"\w+", inv_item.description.lower()))
                    for p_item in po.items:
                        p_words = set(re.findall(r"\w+", p_item.description.lower()))
                        if inv_words & p_words:
                            matched_po_item = p_item
                            break
                
                # Fallback to single item match if both have 1 item
                if not matched_po_item and len(po.items) == 1 and len(invoice.items) == 1:
                    matched_po_item = po.items[0]

                if not matched_po_item:
                    mismatches.append({
                        "item": inv_item.description,
                        "sku": inv_item.sku,
                        "issue": "unmatched_item",
                        "message": f"Item '{inv_item.description}' not found on PO {po.po_number}"
                    })
                    continue

                # Check quantity
                qty_diff = abs(inv_item.quantity - matched_po_item.quantity)
                max_qty_diff = matched_po_item.quantity * qty_tolerance
                if qty_diff > max_qty_diff:
                    mismatches.append({
                        "item": inv_item.description,
                        "sku": inv_item.sku,
                        "issue": "quantity_mismatch",
                        "invoice_qty": inv_item.quantity,
                        "po_qty": matched_po_item.quantity,
                        "difference": round(qty_diff, 2),
                        "allowed_diff": round(max_qty_diff, 2)
                    })

                # Check unit price
                price_diff = abs(inv_item.unit_price - matched_po_item.unit_price)
                max_price_diff = matched_po_item.unit_price * price_tolerance
                if price_diff > max_price_diff:
                    mismatches.append({
                        "item": inv_item.description,
                        "sku": inv_item.sku,
                        "issue": "price_mismatch",
                        "invoice_price": inv_item.unit_price,
                        "po_price": matched_po_item.unit_price,
                        "difference": round(price_diff, 2),
                        "allowed_diff": round(max_price_diff, 2)
                    })

        if mismatches:
            return {
                "control": "PO_MATCH",
                "status": ControlStatus.FAIL,
                "severity": ControlSeverity.HIGH,
                "message": f"PO {po.po_number} match failed with {len(mismatches)} item/pricing discrepancies",
                "details": {
                    "po_number": po.po_number,
                    "mismatches": mismatches
                }
            }

        return {
            "control": "PO_MATCH",
            "status": ControlStatus.PASS,
            "severity": ControlSeverity.NONE,
            "message": f"Invoice matched PO {po.po_number} within ±{price_tolerance*100:.0f}% tolerance",
            "details": {
                "po_number": po.po_number,
                "invoice_total": invoice.total_amount,
                "po_total": po.total_amount
            }
        }
