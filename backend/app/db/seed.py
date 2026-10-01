"""
Optional seed data for development/testing.
This creates realistic data scenarios for testing the control engine.
The application MUST work without this data (empty states).
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from ..models import (
    Vendor, VendorStatus,
    PurchaseOrder, PurchaseOrderItem, POStatus,
    GoodsReceipt, GoodsReceiptItem, ReceiptStatus,
    Invoice, InvoiceItem, InvoiceStatus
)

def create_seed_data(db: Session):
    """Create seed data for testing"""
    
    # Create Vendors
    vendor1 = Vendor(
        vendor_code="V001",
        name="Acme Corporation",
        tax_id="12-3456789",
        email="accounting@acme.com",
        status=VendorStatus.ACTIVE,
        payment_terms="Net 30"
    )
    vendor2 = Vendor(
        vendor_code="V002",
        name="Global Supplies Inc",
        tax_id="98-7654321",
        email="billing@globalsupplies.com",
        status=VendorStatus.ACTIVE,
        payment_terms="Net 45"
    )
    vendor3 = Vendor(
        vendor_code="V003",
        name="Blocked Vendor LLC",
        tax_id="11-2233445",
        email="contact@blocked.com",
        status=VendorStatus.BLOCKED,
        payment_terms="Net 30"
    )
    
    db.add_all([vendor1, vendor2, vendor3])
    db.flush()
    
    # Create Purchase Orders
    po1 = PurchaseOrder(
        po_number="PO-2024-001",
        vendor_id=vendor1.id,
        po_date=datetime.utcnow() - timedelta(days=30),
        currency="USD",
        status=POStatus.RECEIVED,
        total_amount=5000.00
    )
    
    po1_item1 = PurchaseOrderItem(
        purchase_order_id=None,  # Will be set after flush
        description="Widget Pro Model A",
        sku="WID-PRO-A",
        quantity=100,
        unit_price=40.00,
        tax_rate=0.08,
        line_total=4000.00
    )
    
    po1_item2 = PurchaseOrderItem(
        purchase_order_id=None,
        description="Premium Service Package",
        sku="SVC-PREM",
        quantity=10,
        unit_price=100.00,
        tax_rate=0.08,
        line_total=1000.00
    )
    
    db.add(po1)
    db.flush()
    
    po1_item1.purchase_order_id = po1.id
    po1_item2.purchase_order_id = po1.id
    db.add_all([po1_item1, po1_item2])
    db.flush()
    
    # Create Goods Receipt for PO1
    receipt1 = GoodsReceipt(
        receipt_number="GR-2024-001",
        purchase_order_id=po1.id,
        received_date=datetime.utcnow() - timedelta(days=15),
        status=ReceiptStatus.RECEIVED
    )
    
    db.add(receipt1)
    db.flush()
    
    receipt1_item1 = GoodsReceiptItem(
        goods_receipt_id=receipt1.id,
        po_item_id=po1_item1.id,
        quantity_received=100
    )
    
    receipt1_item2 = GoodsReceiptItem(
        goods_receipt_id=receipt1.id,
        po_item_id=po1_item2.id,
        quantity_received=10
    )
    
    db.add_all([receipt1_item1, receipt1_item2])
    
    # Create PO2 for quantity mismatch scenario
    po2 = PurchaseOrder(
        po_number="PO-2024-002",
        vendor_id=vendor2.id,
        po_date=datetime.utcnow() - timedelta(days=20),
        currency="USD",
        status=POStatus.PARTIALLY_RECEIVED,
        total_amount=10000.00
    )
    
    db.add(po2)
    db.flush()
    
    po2_item1 = PurchaseOrderItem(
        purchase_order_id=po2.id,
        description="Equipment Unit XL",
        sku="EQP-XL",
        quantity=50,
        unit_price=200.00,
        tax_rate=0.08,
        line_total=10000.00
    )
    
    db.add(po2_item1)
    db.flush()
    
    # Partial receipt for PO2 (only 30 out of 50)
    receipt2 = GoodsReceipt(
        receipt_number="GR-2024-002",
        purchase_order_id=po2.id,
        received_date=datetime.utcnow() - timedelta(days=10),
        status=ReceiptStatus.RECEIVED
    )
    
    db.add(receipt2)
    db.flush()
    
    receipt2_item1 = GoodsReceiptItem(
        goods_receipt_id=receipt2.id,
        po_item_id=po2_item1.id,
        quantity_received=30  # Less than ordered
    )
    
    db.add(receipt2_item1)
    
    db.commit()
    
    print("Seed data created successfully!")
    print(f"Created vendors: {vendor1.name}, {vendor2.name}, {vendor3.name}")
    print(f"Created POs: {po1.po_number}, {po2.po_number}")
    print(f"Created receipts: {receipt1.receipt_number}, {receipt2.receipt_number}")

if __name__ == "__main__":
    from ..database import SessionLocal
    db = SessionLocal()
    try:
        create_seed_data(db)
    finally:
        db.close()
