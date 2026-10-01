import re
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from ..models import Invoice, GoodsReceipt, PurchaseOrder, ControlStatus, ControlSeverity
from .settings_service import get_all_settings

class ReceiptMatching:
    def __init__(self, db: Session):
        self.db = db
    
    def _get_qty_tolerance(self) -> float:
        settings = get_all_settings(self.db)
        return float(settings.get("po_quantity_tolerance", 0.05))
    
    async def verify_receipt(self, invoice: Invoice) -> Dict[str, Any]:
        """Verify goods/services received against purchase order receipts"""
        qty_tolerance = self._get_qty_tolerance()

        if not invoice.po_id:
            return {
                "control": "RECEIPT_VERIFICATION",
                "status": ControlStatus.WARNING,
                "severity": ControlSeverity.MEDIUM,
                "message": "Invoice has no PO reference; cannot verify goods receipt",
                "details": {}
            }
        
        po = self.db.query(PurchaseOrder).filter(PurchaseOrder.id == invoice.po_id).first()
        po_number = po.po_number if po else f"ID#{invoice.po_id}"

        receipts = self.db.query(GoodsReceipt).filter(
            GoodsReceipt.purchase_order_id == invoice.po_id
        ).all()
        
        if not receipts:
            return {
                "control": "RECEIPT_VERIFICATION",
                "status": ControlStatus.FAIL,
                "severity": ControlSeverity.CRITICAL,
                "message": f"No goods receipt record found for PO {po_number}. Goods/services have not been verified as received",
                "details": {"po_id": invoice.po_id, "po_number": po_number}
            }
        
        receipt_numbers = [r.receipt_number for r in receipts]
        
        # Verify quantities per line item
        shortages: List[Dict[str, Any]] = []
        if invoice.items:
            for inv_item in invoice.items:
                total_received = 0.0
                
                for receipt in receipts:
                    for r_item in receipt.items:
                        # Check match by PO item SKU or description
                        po_item = r_item.po_item
                        if not po_item:
                            continue
                        
                        match = False
                        if inv_item.sku and po_item.sku:
                            match = (inv_item.sku.strip().lower() == po_item.sku.strip().lower())
                        
                        if not match and inv_item.description and po_item.description:
                            inv_words = set(re.findall(r"\w+", inv_item.description.lower()))
                            po_words = set(re.findall(r"\w+", po_item.description.lower()))
                            match = bool(inv_words & po_words)
                        
                        if not match and len(invoice.items) == 1 and len(receipt.items) == 1:
                            match = True

                        if match:
                            total_received += float(r_item.quantity_received)
                
                shortage = inv_item.quantity - total_received
                allowed_tolerance = inv_item.quantity * qty_tolerance
                
                if shortage > allowed_tolerance:
                    shortages.append({
                        "item": inv_item.description,
                        "sku": inv_item.sku,
                        "billed_quantity": inv_item.quantity,
                        "received_quantity": total_received,
                        "shortage": round(shortage, 2),
                        "allowed_tolerance": round(allowed_tolerance, 2)
                    })
        
        if shortages:
            return {
                "control": "RECEIPT_VERIFICATION",
                "status": ControlStatus.FAIL,
                "severity": ControlSeverity.HIGH,
                "message": f"Insufficient goods received for PO {po_number}: {len(shortages)} item(s) have quantity shortages",
                "details": {
                    "po_number": po_number,
                    "receipts": receipt_numbers,
                    "shortages": shortages
                }
            }
        
        return {
            "control": "RECEIPT_VERIFICATION",
            "status": ControlStatus.PASS,
            "severity": ControlSeverity.NONE,
            "message": f"Goods receipt verified ({len(receipts)} receipt(s): {', '.join(receipt_numbers)})",
            "details": {
                "po_number": po_number,
                "receipt_count": len(receipts),
                "receipts": receipt_numbers
            }
        }
