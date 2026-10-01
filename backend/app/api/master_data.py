from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from ..database import get_db
from ..models import (
    Vendor, VendorStatus,
    PurchaseOrder, PurchaseOrderItem, POStatus,
    GoodsReceipt, GoodsReceiptItem, ReceiptStatus
)

router = APIRouter(prefix="/api/master", tags=["master-data"])

class VendorCreate(BaseModel):
    vendor_code: str = Field(..., min_length=2)
    name: str = Field(..., min_length=2)
    tax_id: Optional[str] = None
    email: Optional[str] = None
    status: Optional[VendorStatus] = VendorStatus.ACTIVE
    payment_terms: Optional[str] = "Net 30"

class POItemCreate(BaseModel):
    description: str
    sku: Optional[str] = None
    quantity: float = Field(..., gt=0)
    unit_price: float = Field(..., ge=0)
    tax_rate: Optional[float] = 0.0

class POCreate(BaseModel):
    po_number: str = Field(..., min_length=2)
    vendor_id: int
    currency: Optional[str] = "USD"
    items: List[POItemCreate]

class GRItemCreate(BaseModel):
    po_item_id: int
    quantity_received: float = Field(..., gt=0)

class GRCreate(BaseModel):
    receipt_number: str = Field(..., min_length=2)
    purchase_order_id: int
    items: List[GRItemCreate]

# --- Vendors ---
@router.get("/vendors")
def list_vendors(db: Session = Depends(get_db)):
    vendors = db.query(Vendor).order_by(Vendor.name).all()
    return [
        {
            "id": v.id,
            "vendor_code": v.vendor_code,
            "name": v.name,
            "tax_id": v.tax_id,
            "email": v.email,
            "status": v.status.value,
            "payment_terms": v.payment_terms
        }
        for v in vendors
    ]

@router.post("/vendors")
def create_vendor(data: VendorCreate, db: Session = Depends(get_db)):
    existing = db.query(Vendor).filter(
        (Vendor.vendor_code == data.vendor_code) | (Vendor.name == data.name)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Vendor code or name already exists")
    
    vendor = Vendor(
        vendor_code=data.vendor_code,
        name=data.name,
        tax_id=data.tax_id,
        email=data.email,
        status=data.status,
        payment_terms=data.payment_terms
    )
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    return {"id": vendor.id, "vendor_code": vendor.vendor_code, "name": vendor.name, "status": vendor.status.value}

# --- Purchase Orders ---
@router.get("/purchase-orders")
def list_purchase_orders(db: Session = Depends(get_db)):
    pos = db.query(PurchaseOrder).order_by(PurchaseOrder.created_at.desc()).all()
    return [
        {
            "id": po.id,
            "po_number": po.po_number,
            "vendor_id": po.vendor_id,
            "vendor_name": po.vendor.name if po.vendor else "Unknown",
            "total_amount": po.total_amount,
            "currency": po.currency,
            "status": po.status.value,
            "items": [
                {
                    "id": item.id,
                    "description": item.description,
                    "sku": item.sku,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "line_total": item.line_total
                }
                for item in po.items
            ]
        }
        for po in pos
    ]

@router.post("/purchase-orders")
def create_purchase_order(data: POCreate, db: Session = Depends(get_db)):
    vendor = db.query(Vendor).filter(Vendor.id == data.vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    existing = db.query(PurchaseOrder).filter(PurchaseOrder.po_number == data.po_number).first()
    if existing:
        raise HTTPException(status_code=400, detail="PO number already exists")

    total_amount = sum(item.quantity * item.unit_price for item in data.items)

    po = PurchaseOrder(
        po_number=data.po_number,
        vendor_id=data.vendor_id,
        po_date=datetime.utcnow(),
        currency=data.currency or "USD",
        status=POStatus.OPEN,
        total_amount=round(total_amount, 2)
    )
    db.add(po)
    db.flush()

    for item in data.items:
        db.add(PurchaseOrderItem(
            purchase_order_id=po.id,
            description=item.description,
            sku=item.sku,
            quantity=item.quantity,
            unit_price=item.unit_price,
            tax_rate=item.tax_rate or 0.0,
            line_total=round(item.quantity * item.unit_price, 2)
        ))
    
    db.commit()
    db.refresh(po)
    return {"id": po.id, "po_number": po.po_number, "total_amount": po.total_amount, "status": po.status.value}

# --- Goods Receipts ---
@router.post("/goods-receipts")
def create_goods_receipt(data: GRCreate, db: Session = Depends(get_db)):
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == data.purchase_order_id).first()
    if not po:
        raise HTTPException(status_code=404, detail="PO not found")

    gr = GoodsReceipt(
        receipt_number=data.receipt_number,
        purchase_order_id=po.id,
        received_date=datetime.utcnow(),
        status=ReceiptStatus.RECEIVED
    )
    db.add(gr)
    db.flush()

    for item in data.items:
        db.add(GoodsReceiptItem(
            goods_receipt_id=gr.id,
            po_item_id=item.po_item_id,
            quantity_received=item.quantity_received
        ))
    
    po.status = POStatus.RECEIVED
    db.commit()
    db.refresh(gr)
    return {"id": gr.id, "receipt_number": gr.receipt_number, "purchase_order_id": gr.purchase_order_id}
