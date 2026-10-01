from typing import Dict, Any
from sqlalchemy.orm import Session
from ..models import Invoice, GoodsReceipt, ControlStatus, ControlSeverity
from ..config import get_settings

settings = get_settings()

class ReceiptMatching:
    def __init__(self, db: Session):
        self.db = db
        self.quantity_tolerance = settings.po_quantity_tolerance
    
    async def verify_receipt(self, invoice: Invoice) -> Dict[str, Any]:
        """Verify goods/services have been received"""
        if not invoice.po_id:
            return {
                "control": "RECEIPT_VERIFICATION",
                "status": ControlStatus.WARNING,
                "severity": ControlSeverity.LOW,
                "message": "No PO to verify receipts against",
                "details": {}
            }
        
        # Get all receipts for this PO
        receipts = self.db.query(GoodsReceipt).filter(
            GoodsReceipt.purchase_order_id == invoice.po_id
        ).all()
        
        if not receipts:
            return {
                "control": "RECEIPT_VERIFICATION",
                "status": ControlStatus.FAIL,
                "severity": ControlSeverity.CRITICAL,
                "message": "No goods receipt found for purchase order",
                "details": {"po_id": invoice.po_id}
            }
        
        # Verify received quantities match or exceed invoice quantities
        if invoice.items:
            for inv_item in invoice.items:
                total_received = 0
                
                # Sum up all received quantities for this item
                for receipt in receipts:
                    for receipt_item in receipt.items:
                        if receipt_item.po_item and inv_item.sku == receipt_item.po_item.sku:
                            total_received += receipt_item.quantity_received
                
                # Check if received quantity is sufficient
                qty_diff = inv_item.quantity - total_received
                tolerance = inv_item.quantity * self.quantity_tolerance
                
                if qty_diff > tolerance:
                    return {
                        "control": "RECEIPT_VERIFICATION",
                        "status": ControlStatus.FAIL,
                        "severity": ControlSeverity.HIGH,
                        "message": f"Insufficient receipt quantity for item {inv_item.sku}",
                        "details": {
                            "sku": inv_item.sku,
                            "invoice_quantity": inv_item.quantity,
                            "received_quantity": total_received,
                            "shortage": qty_diff
                        }
                    }
        
        return {
            "control": "RECEIPT_VERIFICATION",
            "status": ControlStatus.PASS,
            "severity": ControlSeverity.NONE,
            "message": "Goods receipt verified successfully",
            "details": {"receipt_count": len(receipts)}
        }
