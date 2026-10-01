from typing import Dict, Any
from sqlalchemy.orm import Session
from ..models import Invoice, PurchaseOrder, ControlStatus, ControlSeverity
from ..config import get_settings

settings = get_settings()

class POMatching:
    def __init__(self, db: Session):
        self.db = db
        self.price_tolerance = settings.po_price_tolerance
        self.quantity_tolerance = settings.po_quantity_tolerance
    
    async def match_po(self, invoice: Invoice) -> Dict[str, Any]:
        """Match invoice against purchase order"""
        if not invoice.po_id:
            return {
                "control": "PO_MATCH",
                "status": ControlStatus.WARNING,
                "severity": ControlSeverity.MEDIUM,
                "message": "No purchase order specified",
                "details": {}
            }
        
        po = self.db.query(PurchaseOrder).filter(PurchaseOrder.id == invoice.po_id).first()
        
        if not po:
            return {
                "control": "PO_MATCH",
                "status": ControlStatus.FAIL,
                "severity": ControlSeverity.CRITICAL,
                "message": "Purchase order not found",
                "details": {"po_id": invoice.po_id}
            }
        
        # Verify vendor matches
        if po.vendor_id != invoice.vendor_id:
            return {
                "control": "PO_MATCH",
                "status": ControlStatus.FAIL,
                "severity": ControlSeverity.CRITICAL,
                "message": "Invoice vendor does not match PO vendor",
                "details": {
                    "invoice_vendor_id": invoice.vendor_id,
                    "po_vendor_id": po.vendor_id
                }
            }
        
        # Verify amount within tolerance
        amount_diff = abs(invoice.total_amount - po.total_amount)
        amount_tolerance = po.total_amount * self.price_tolerance
        
        if amount_diff > amount_tolerance:
            return {
                "control": "PO_MATCH",
                "status": ControlStatus.FAIL,
                "severity": ControlSeverity.HIGH,
                "message": f"Invoice amount differs from PO by {amount_diff:.2f} (tolerance: {amount_tolerance:.2f})",
                "details": {
                    "invoice_amount": invoice.total_amount,
                    "po_amount": po.total_amount,
                    "difference": amount_diff,
                    "tolerance": amount_tolerance
                }
            }
        
        # Verify line items match (if present)
        if invoice.items and po.items:
            item_mismatches = []
            
            for inv_item in invoice.items:
                # Find matching PO item by SKU or description
                po_item = None
                for po_i in po.items:
                    if inv_item.sku and po_i.sku == inv_item.sku:
                        po_item = po_i
                        break
                
                if po_item:
                    # Check quantity tolerance
                    qty_diff = abs(inv_item.quantity - po_item.quantity)
                    qty_tolerance = po_item.quantity * self.quantity_tolerance
                    
                    if qty_diff > qty_tolerance:
                        item_mismatches.append({
                            "sku": inv_item.sku,
                            "issue": "quantity_mismatch",
                            "invoice_qty": inv_item.quantity,
                            "po_qty": po_item.quantity
                        })
                    
                    # Check price tolerance
                    price_diff = abs(inv_item.unit_price - po_item.unit_price)
                    price_tolerance_val = po_item.unit_price * self.price_tolerance
                    
                    if price_diff > price_tolerance_val:
                        item_mismatches.append({
                            "sku": inv_item.sku,
                            "issue": "price_mismatch",
                            "invoice_price": inv_item.unit_price,
                            "po_price": po_item.unit_price
                        })
            
            if item_mismatches:
                return {
                    "control": "PO_MATCH",
                    "status": ControlStatus.FAIL,
                    "severity": ControlSeverity.HIGH,
                    "message": f"Found {len(item_mismatches)} line item mismatches",
                    "details": {"mismatches": item_mismatches}
                }
        
        return {
            "control": "PO_MATCH",
            "status": ControlStatus.PASS,
            "severity": ControlSeverity.NONE,
            "message": "Invoice matches purchase order within tolerance",
            "details": {
                "po_number": po.po_number,
                "invoice_amount": invoice.total_amount,
                "po_amount": po.total_amount
            }
        }
