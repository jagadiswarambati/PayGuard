from typing import List, Dict, Any
from sqlalchemy.orm import Session
from ..models import (
    Invoice, ControlResult, ControlStatus, ControlSeverity,
    Exception, ExceptionType, ExceptionSeverity, ExceptionStatus,
    AuditEvent, AuditAction, ActorType
)
from .vendor_control import VendorControl
from .po_matching import POMatching
from .receipt_matching import ReceiptMatching
from .duplicate_detection import DuplicateDetection
from .financial_validation import FinancialValidation
from .approval_engine import ApprovalEngine

class ControlEngine:
    def __init__(self, db: Session):
        self.db = db
        self.vendor_control = VendorControl(db)
        self.po_matching = POMatching(db)
        self.receipt_matching = ReceiptMatching(db)
        self.duplicate_detection = DuplicateDetection(db)
        self.financial_validation = FinancialValidation(db)
        self.approval_engine = ApprovalEngine(db)
    
    async def process_invoice(self, invoice: Invoice) -> Dict[str, Any]:
        """Run all controls on an invoice and return decision"""
        results = {
            "invoice_id": invoice.id,
            "controls": [],
            "decision": "PENDING",
            "exceptions": [],
            "requires_approval": False
        }
        
        # Update invoice status
        invoice.status = "PROCESSING"
        self.db.commit()
        
        # Run all controls
        control_results = []
        
        # 1. Vendor Verification
        vendor_result = await self.vendor_control.verify_vendor(invoice)
        control_results.append(vendor_result)
        self._save_control_result(invoice.id, vendor_result)
        
        # 2. PO Matching (if PO specified)
        if invoice.po_id:
            po_result = await self.po_matching.match_po(invoice)
            control_results.append(po_result)
            self._save_control_result(invoice.id, po_result)
            
            # 3. Receipt Verification
            receipt_result = await self.receipt_matching.verify_receipt(invoice)
            control_results.append(receipt_result)
            self._save_control_result(invoice.id, receipt_result)
        
        # 4. Duplicate Detection
        duplicate_result = await self.duplicate_detection.check_duplicate(invoice)
        control_results.append(duplicate_result)
        self._save_control_result(invoice.id, duplicate_result)
        
        # 5. Financial Validation
        financial_result = await self.financial_validation.validate_financials(invoice)
        control_results.append(financial_result)
        self._save_control_result(invoice.id, financial_result)
        
        # Analyze results and create exceptions
        failed_controls = [r for r in control_results if r["status"] == ControlStatus.FAIL]
        
        if failed_controls:
            # Create exceptions for failed controls
            for control in failed_controls:
                self._create_exception(invoice.id, control)
                results["exceptions"].append(control["control"])
            
            invoice.status = "PENDING_REVIEW"
            results["decision"] = "EXCEPTION"
        else:
            # All controls passed - check approval requirements
            approval_result = await self.approval_engine.determine_approval(invoice)
            
            if approval_result["requires_approval"]:
                invoice.status = "PENDING_REVIEW"
                results["decision"] = "APPROVAL_REQUIRED"
                results["requires_approval"] = True
                
                # Create approval records
                await self.approval_engine.create_approvals(invoice, approval_result["level"])
            else:
                invoice.status = "APPROVED"
                results["decision"] = "APPROVED"
                
                # Auto-create payable obligation
                await self.approval_engine.create_payable_obligation(invoice)
        
        self.db.commit()
        results["controls"] = [self._control_to_dict(r) for r in control_results]
        
        return results
    
    def _save_control_result(self, invoice_id: int, result: Dict[str, Any]):
        """Save control result to database"""
        control_result = ControlResult(
            invoice_id=invoice_id,
            control_name=result["control"],
            status=result["status"],
            severity=result["severity"],
            message=result["message"],
            details=result.get("details", {})
        )
        self.db.add(control_result)
        
        # Create audit event
        audit = AuditEvent(
            entity_type="Invoice",
            entity_id=invoice_id,
            action=AuditAction.FINANCIAL_CHECKED,
            actor_type=ActorType.SYSTEM,
            result=result["status"].value,
            metadata={"control": result["control"], "message": result["message"]}
        )
        self.db.add(audit)
    
    def _create_exception(self, invoice_id: int, control_result: Dict[str, Any]):
        """Create exception for failed control"""
        exception_type_map = {
            "VENDOR_VERIFICATION": ExceptionType.VENDOR_NOT_FOUND,
            "PO_MATCH": ExceptionType.PO_NOT_FOUND,
            "RECEIPT_VERIFICATION": ExceptionType.RECEIPT_MISSING,
            "DUPLICATE_CHECK": ExceptionType.DUPLICATE_INVOICE,
            "FINANCIAL_VALIDATION": ExceptionType.FINANCIAL_MISMATCH
        }
        
        exception_type = exception_type_map.get(
            control_result["control"],
            ExceptionType.FINANCIAL_MISMATCH
        )
        
        exception = Exception(
            invoice_id=invoice_id,
            type=exception_type,
            severity=ExceptionSeverity.HIGH if control_result["severity"] == ControlSeverity.CRITICAL else ExceptionSeverity.MEDIUM,
            status=ExceptionStatus.OPEN,
            message=control_result["message"]
        )
        self.db.add(exception)
        
        # Create audit event
        audit = AuditEvent(
            entity_type="Invoice",
            entity_id=invoice_id,
            action=AuditAction.EXCEPTION_CREATED,
            actor_type=ActorType.SYSTEM,
            result="EXCEPTION_CREATED",
            metadata={"type": exception_type.value, "message": control_result["message"]}
        )
        self.db.add(audit)
    
    def _control_to_dict(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Convert control result to serializable dict"""
        return {
            "control": result["control"],
            "status": result["status"].value,
            "severity": result["severity"].value,
            "message": result["message"],
            "details": result.get("details", {})
        }
