from typing import Dict, Any
from sqlalchemy.orm import Session
from ..models import Invoice, Vendor, VendorStatus, ControlStatus, ControlSeverity

class VendorControl:
    def __init__(self, db: Session):
        self.db = db
    
    async def verify_vendor(self, invoice: Invoice) -> Dict[str, Any]:
        """Verify vendor exists, is active, and not blocked"""
        vendor = self.db.query(Vendor).filter(Vendor.id == invoice.vendor_id).first()
        
        if not vendor:
            return {
                "control": "VENDOR_VERIFICATION",
                "status": ControlStatus.FAIL,
                "severity": ControlSeverity.CRITICAL,
                "message": "Vendor not found in system",
                "details": {"vendor_id": invoice.vendor_id}
            }
        
        if vendor.status == VendorStatus.BLOCKED:
            return {
                "control": "VENDOR_VERIFICATION",
                "status": ControlStatus.FAIL,
                "severity": ControlSeverity.CRITICAL,
                "message": f"Vendor {vendor.name} is blocked",
                "details": {"vendor_id": vendor.id, "vendor_name": vendor.name}
            }
        
        if vendor.status == VendorStatus.INACTIVE:
            return {
                "control": "VENDOR_VERIFICATION",
                "status": ControlStatus.WARNING,
                "severity": ControlSeverity.MEDIUM,
                "message": f"Vendor {vendor.name} is inactive",
                "details": {"vendor_id": vendor.id, "vendor_name": vendor.name}
            }
        
        return {
            "control": "VENDOR_VERIFICATION",
            "status": ControlStatus.PASS,
            "severity": ControlSeverity.NONE,
            "message": f"Vendor {vendor.name} verified successfully",
            "details": {"vendor_id": vendor.id, "vendor_name": vendor.name}
        }
