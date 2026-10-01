import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from ..models import (
    Invoice, InvoiceStatus, ControlResult, ControlStatus, ControlSeverity,
    Exception as InvoiceException, ExceptionType, ExceptionSeverity, ExceptionStatus,
    AuditEvent, AuditAction, ActorType
)
from .vendor_control import VendorControl
from .po_matching import POMatching
from .receipt_matching import ReceiptMatching
from .duplicate_detection import DuplicateDetection
from .financial_validation import FinancialValidation
from .approval_engine import ApprovalEngine

logger = logging.getLogger("payguard.control_engine")

class ControlEngine:
    def __init__(self, db: Session):
        self.db = db
        self.vendor_control = VendorControl(db)
        self.po_matching = POMatching(db)
        self.receipt_matching = ReceiptMatching(db)
        self.duplicate_detection = DuplicateDetection(db)
        self.financial_validation = FinancialValidation(db)
        self.approval_engine = ApprovalEngine(db)
    
    async def process_invoice(self, invoice: Invoice, submitted_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Run all deterministic AP controls on an invoice and execute decision logic"""
        submitted_data = submitted_data or {}
        
        # Clear any prior control results to allow clean re-runs
        self.db.query(ControlResult).filter(ControlResult.invoice_id == invoice.id).delete()
        self.db.flush()

        invoice.status = InvoiceStatus.PROCESSING
        self.db.commit()

        control_results: List[Dict[str, Any]] = []

        # 1. VENDOR VERIFICATION
        vendor_result = await self.vendor_control.verify_vendor(
            invoice=invoice,
            extracted_vendor_name=submitted_data.get("vendor_name") or (invoice.vendor.name if invoice.vendor else None),
            extracted_tax_id=submitted_data.get("tax_id")
        )
        control_results.append(vendor_result)
        self._save_control_result(invoice.id, vendor_result, AuditAction.VENDOR_VERIFIED)

        # 2. PURCHASE ORDER MATCHING
        po_number_ref = submitted_data.get("po_number") or (invoice.purchase_order.po_number if invoice.purchase_order else None)
        po_result = await self.po_matching.match_po(invoice=invoice, submitted_po_number=po_number_ref)
        control_results.append(po_result)
        po_action = AuditAction.PO_MATCHED if po_result["status"] == ControlStatus.PASS else AuditAction.PO_MISMATCH
        self._save_control_result(invoice.id, po_result, po_action)

        # 3. GOODS / SERVICE RECEIPT VERIFICATION
        receipt_result = await self.receipt_matching.verify_receipt(invoice=invoice)
        control_results.append(receipt_result)
        self._save_control_result(invoice.id, receipt_result, AuditAction.RECEIPT_VERIFIED)

        # 4. DUPLICATE DETECTION
        dup_result = await self.duplicate_detection.check_duplicate(invoice=invoice)
        control_results.append(dup_result)
        self._save_control_result(invoice.id, dup_result, AuditAction.DUPLICATE_CHECKED)

        # 5. FINANCIAL VALIDATION
        fin_result = await self.financial_validation.validate_financials(invoice=invoice)
        control_results.append(fin_result)
        self._save_control_result(invoice.id, fin_result, AuditAction.FINANCIAL_CHECKED)

        # EVALUATE DECISION ENGINE
        failed_controls = [r for r in control_results if r["status"] == ControlStatus.FAIL]
        warning_controls = [r for r in control_results if r["status"] == ControlStatus.WARNING]

        results = {
            "invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "controls": [self._control_to_dict(r) for r in control_results],
            "exceptions": [],
            "decision": "PENDING",
            "decision_reason": "",
            "requires_approval": False
        }

        if failed_controls:
            # Check if auto-rejection applies (e.g. Blocked Vendor or Exact Duplicate)
            has_blocked_vendor = any("BLOCKED" in f["message"].upper() for f in failed_controls)
            has_duplicate = any("DUPLICATE" in f["control"].upper() for f in failed_controls)

            # Create exceptions for failed controls
            for control in failed_controls:
                exc = self._create_exception(invoice.id, control)
                results["exceptions"].append({
                    "id": exc.id,
                    "type": exc.type.value,
                    "severity": exc.severity.value,
                    "message": exc.message
                })

            if has_blocked_vendor:
                invoice.status = InvoiceStatus.REJECTED
                results["decision"] = "REJECTED"
                results["decision_reason"] = "Invoice automatically rejected due to blocked vendor"
            elif has_duplicate:
                invoice.status = InvoiceStatus.ON_HOLD
                results["decision"] = "ON_HOLD"
                results["decision_reason"] = "Invoice placed ON HOLD due to duplicate detection failure"
            else:
                invoice.status = InvoiceStatus.PENDING_REVIEW
                results["decision"] = "EXCEPTION"
                results["decision_reason"] = f"Invoice triggered {len(failed_controls)} control exception(s) requiring review or override"

        else:
            # All mandatory controls satisfied! Proceed to Approval Workflow
            approval_res = await self.approval_engine.determine_approval(invoice)
            
            if approval_res["requires_approval"]:
                invoice.status = InvoiceStatus.PENDING_REVIEW
                results["decision"] = "APPROVED_FOR_APPROVAL"
                results["decision_reason"] = approval_res["reason"]
                results["requires_approval"] = True
                await self.approval_engine.create_approvals(invoice, approval_res["levels"])
            else:
                # Automatic approval (< ₹5,000 threshold)
                invoice.status = InvoiceStatus.APPROVED
                results["decision"] = "APPROVED"
                results["decision_reason"] = "All controls passed and amount qualifies for automatic approval"
                await self.approval_engine.create_payable_obligation(invoice)

        self.db.commit()
        return results

    def _save_control_result(self, invoice_id: int, result: Dict[str, Any], action: AuditAction):
        """Persist individual control result and corresponding audit event"""
        cr = ControlResult(
            invoice_id=invoice_id,
            control_name=result["control"],
            status=result["status"],
            severity=result["severity"],
            message=result["message"],
            details=result.get("details", {})
        )
        self.db.add(cr)
        
        audit = AuditEvent(
            entity_type="Invoice",
            entity_id=invoice_id,
            action=action,
            actor_type=ActorType.SYSTEM,
            result=result["status"].value,
            event_metadata={
                "control": result["control"],
                "severity": result["severity"].value,
                "message": result["message"]
            }
        )
        self.db.add(audit)

    def _create_exception(self, invoice_id: int, control_result: Dict[str, Any]) -> InvoiceException:
        """Map failed control to specific exception type and record in DB"""
        ctrl = control_result["control"]
        msg = control_result.get("message", "").lower()
        details = control_result.get("details", {})

        exc_type = InvoiceExceptionType = ExceptionType.FINANCIAL_MISMATCH

        if ctrl == "VENDOR_VERIFICATION":
            if "blocked" in msg:
                exc_type = ExceptionType.VENDOR_BLOCKED
            else:
                exc_type = ExceptionType.VENDOR_NOT_FOUND

        elif ctrl == "PO_MATCH":
            if "vendor does not match" in msg:
                exc_type = ExceptionType.PO_VENDOR_MISMATCH
            elif "not found" in msg:
                exc_type = ExceptionType.PO_NOT_FOUND
            elif "price" in msg:
                exc_type = ExceptionType.PRICE_MISMATCH
            elif "quantity" in msg:
                exc_type = ExceptionType.QUANTITY_MISMATCH
            else:
                exc_type = ExceptionType.PO_NOT_FOUND

        elif ctrl == "RECEIPT_VERIFICATION":
            if "no goods receipt" in msg:
                exc_type = ExceptionType.RECEIPT_MISSING
            else:
                exc_type = ExceptionType.RECEIPT_QUANTITY_INSUFFICIENT

        elif ctrl == "DUPLICATE_CHECK":
            exc_type = ExceptionType.DUPLICATE_INVOICE

        elif ctrl == "FINANCIAL_VALIDATION":
            if "tax" in msg:
                exc_type = ExceptionType.TAX_MISMATCH
            else:
                exc_type = ExceptionType.FINANCIAL_MISMATCH

        severity = (
            ExceptionSeverity.CRITICAL if control_result["severity"] == ControlSeverity.CRITICAL
            else ExceptionSeverity.HIGH if control_result["severity"] == ControlSeverity.HIGH
            else ExceptionSeverity.MEDIUM
        )

        # Check if an open exception of this type already exists on this invoice
        existing = self.db.query(InvoiceException).filter(
            InvoiceException.invoice_id == invoice_id,
            InvoiceException.type == exc_type,
            InvoiceException.status == ExceptionStatus.OPEN
        ).first()

        if existing:
            existing.message = control_result["message"]
            return existing

        exc = InvoiceException(
            invoice_id=invoice_id,
            type=exc_type,
            severity=severity,
            status=ExceptionStatus.OPEN,
            message=control_result["message"]
        )
        self.db.add(exc)
        self.db.flush()

        audit = AuditEvent(
            entity_type="Invoice",
            entity_id=invoice_id,
            action=AuditAction.EXCEPTION_CREATED,
            actor_type=ActorType.SYSTEM,
            result="EXCEPTION_CREATED",
            event_metadata={
                "exception_id": exc.id,
                "type": exc_type.value,
                "severity": severity.value,
                "message": control_result["message"]
            }
        )
        self.db.add(audit)
        return exc

    def _control_to_dict(self, result: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "control": result["control"],
            "status": result["status"].value,
            "severity": result["severity"].value,
            "message": result["message"],
            "details": result.get("details", {})
        }
