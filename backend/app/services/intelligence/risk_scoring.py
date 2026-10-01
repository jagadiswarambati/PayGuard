"""
PayGuard Intelligence Layer — Risk Scoring
==========================================
Computes a composite risk score for an invoice by combining:
  1. Vendor risk (GSTIN missing, new vendor, blocked history)
  2. Transaction risk (amount vs. threshold, payment terms)
  3. PO risk (no matching PO, price tolerance breaches)
  4. Anomaly signals from AnomalyDetectionService

Produces: risk_score (0–100) + risk_category.
Does NOT make decisions — supplies evidence to ControlEngine.
"""

import logging
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from ...models import Invoice, Vendor, PurchaseOrder, Exception as InvoiceException, ExceptionStatus

logger = logging.getLogger("payguard.intelligence.risk_scoring")


class RiskScoringService:
    """
    Computes a composite AP risk score for an invoice.
    Score range: 0 (no risk) to 100 (highest risk).
    """

    def __init__(self, db: Session):
        self.db = db

    def score_invoice(
        self,
        invoice: Invoice,
        anomaly_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Compute composite risk score.

        Returns:
            {
                "risk_score": int (0–100),
                "risk_category": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
                "factors": [...],
            }
        """
        factors = []
        score = 0.0

        # Factor 1: Vendor registration
        vendor = invoice.vendor
        if not vendor:
            factors.append({"factor": "UNREGISTERED_VENDOR", "points": 30, "description": "Invoice vendor is not in vendor master"})
            score += 30
        elif not vendor.gstin:
            factors.append({"factor": "MISSING_GSTIN", "points": 15, "description": "Vendor has no GSTIN on record"})
            score += 15
        elif vendor.status and vendor.status.value == "BLOCKED":
            factors.append({"factor": "BLOCKED_VENDOR", "points": 50, "description": "Vendor is blocked"})
            score += 50

        # Factor 2: No PO reference
        if not invoice.po_id:
            factors.append({"factor": "NO_PO_REFERENCE", "points": 20, "description": "Invoice has no linked Purchase Order"})
            score += 20

        # Factor 3: Amount thresholds (INR)
        amount = invoice.total_amount
        if amount > 500000:
            factors.append({"factor": "HIGH_VALUE", "points": 15, "description": f"High-value invoice ₹{amount:,.2f}"})
            score += 15
        elif amount > 100000:
            factors.append({"factor": "ELEVATED_VALUE", "points": 8, "description": f"Elevated amount ₹{amount:,.2f}"})
            score += 8

        # Factor 4: Anomaly signals
        if anomaly_result:
            anomaly_score = anomaly_result.get("anomaly_score", 0.0)
            if anomaly_score >= 0.7:
                pts = 25
                factors.append({"factor": "HIGH_ANOMALY", "points": pts, "description": f"High anomaly score {anomaly_score:.2f}"})
                score += pts
            elif anomaly_score >= 0.4:
                pts = 12
                factors.append({"factor": "MEDIUM_ANOMALY", "points": pts, "description": f"Medium anomaly score {anomaly_score:.2f}"})
                score += pts

        # Factor 5: Missing GST breakdown when amount > 10,000
        if amount > 10000 and invoice.tax_amount == 0:
            factors.append({"factor": "MISSING_GST", "points": 10, "description": "No GST on invoice above ₹10,000"})
            score += 10

        # Factor 6: Prior open exceptions
        open_exceptions = (
            self.db.query(InvoiceException)
            .filter(
                InvoiceException.invoice_id == invoice.id,
                InvoiceException.status == ExceptionStatus.OPEN,
            )
            .count()
        )
        if open_exceptions > 0:
            pts = min(open_exceptions * 10, 30)
            factors.append({"factor": "OPEN_EXCEPTIONS", "points": pts, "description": f"{open_exceptions} open exception(s)"})
            score += pts

        # Clamp to 0–100
        score = min(100, max(0, int(score)))

        risk_category = (
            "CRITICAL" if score >= 75
            else "HIGH" if score >= 50
            else "MEDIUM" if score >= 25
            else "LOW"
        )

        return {
            "risk_score": score,
            "risk_category": risk_category,
            "factors": factors,
        }
