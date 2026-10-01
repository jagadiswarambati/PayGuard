from typing import Dict, Any
from sqlalchemy.orm import Session
from ..models import Invoice, Vendor, VendorStatus, ControlStatus, ControlSeverity

class VendorControl:
    def __init__(self, db: Session):
        self.db = db
    
    async def verify_vendor(self, invoice: Invoice, extracted_vendor_name: str = None, extracted_tax_id: str = None) -> Dict[str, Any]:
        """Verify vendor exists, is active, not blocked, and tax identity matches"""
        vendor = None
        if invoice.vendor_id:
            vendor = self.db.query(Vendor).filter(Vendor.id == invoice.vendor_id).first()
        elif extracted_vendor_name:
            vendor = self.db.query(Vendor).filter(Vendor.name.ilike(extracted_vendor_name.strip())).first()
        
        if not vendor:
            return {
                "control": "VENDOR_VERIFICATION",
                "status": ControlStatus.FAIL,
                "severity": ControlSeverity.CRITICAL,
                "message": f"Vendor '{extracted_vendor_name or 'Unknown'}' is not registered in the approved vendor master",
                "details": {
                    "vendor_id": invoice.vendor_id,
                    "submitted_vendor_name": extracted_vendor_name
                }
            }
        
        if vendor.status == VendorStatus.BLOCKED:
            return {
                "control": "VENDOR_VERIFICATION",
                "status": ControlStatus.FAIL,
                "severity": ControlSeverity.CRITICAL,
                "message": f"Vendor '{vendor.name}' ({vendor.vendor_code}) is BLOCKED from receiving payments",
                "details": {"vendor_id": vendor.id, "vendor_name": vendor.name, "vendor_code": vendor.vendor_code}
            }
        
        if vendor.status == VendorStatus.INACTIVE:
            return {
                "control": "VENDOR_VERIFICATION",
                "status": ControlStatus.WARNING,
                "severity": ControlSeverity.MEDIUM,
                "message": f"Vendor '{vendor.name}' ({vendor.vendor_code}) is marked as INACTIVE",
                "details": {"vendor_id": vendor.id, "vendor_name": vendor.name, "vendor_code": vendor.vendor_code}
            }
        
        # Tax ID check where available
        tax_warning = None
        if extracted_tax_id and vendor.tax_id:
            if extracted_tax_id.strip().upper() != vendor.tax_id.strip().upper():
                tax_warning = f"Submitted Tax ID '{extracted_tax_id}' does not match registered Tax ID '{vendor.tax_id}'"
        
        if tax_warning:
            return {
                "control": "VENDOR_VERIFICATION",
                "status": ControlStatus.WARNING,
                "severity": ControlSeverity.HIGH,
                "message": tax_warning,
                "details": {
                    "vendor_id": vendor.id,
                    "vendor_name": vendor.name,
                    "registered_tax_id": vendor.tax_id,
                    "submitted_tax_id": extracted_tax_id
                }
            }

        return {
            "control": "VENDOR_VERIFICATION",
            "status": ControlStatus.PASS,
            "severity": ControlSeverity.NONE,
            "message": f"Vendor '{vendor.name}' ({vendor.vendor_code}) is active and verified",
            "details": {
                "vendor_id": vendor.id,
                "vendor_name": vendor.name,
                "vendor_code": vendor.vendor_code,
                "tax_id": vendor.tax_id
            }
        }
