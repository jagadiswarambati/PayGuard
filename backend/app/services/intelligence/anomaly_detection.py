"""
PayGuard Intelligence Layer — Anomaly Detection
================================================
Detects statistical anomalies in invoice amounts using:
  1. Z-score analysis against vendor's historical invoice amounts
  2. Round-number detection (amounts like 50000.00 exactly)
  3. Unusual GST rate detection (non-standard rates)
  4. Line-item price deviation from known PO prices

Produces: anomaly_score (0.0–1.0) + list of anomaly signals.
Does NOT make approval decisions — that is ControlEngine's job.
"""

import math
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from ...models import Invoice, InvoiceItem

logger = logging.getLogger("payguard.intelligence.anomaly_detection")

# Standard Indian GST rates (%)
STANDARD_GST_RATES = {0, 5, 12, 18, 28}
STANDARD_GST_RATES_FLOAT = {0.0, 5.0, 12.0, 18.0, 28.0}


class AnomalyDetectionService:
    """
    Detects financial anomalies in invoices using statistical methods.
    All methods return evidence signals — no approval/rejection decisions.
    """

    ROUND_NUMBER_THRESHOLD = 0.0  # exact round numbers (no cents)
    HIGH_ANOMALY_SCORE = 0.75
    MEDIUM_ANOMALY_SCORE = 0.45
    LOW_ANOMALY_SCORE = 0.20

    def __init__(self, db: Session):
        self.db = db

    def analyze_invoice(self, invoice: Invoice) -> Dict[str, Any]:
        """
        Run full anomaly analysis on an invoice.

        Returns:
            {
                "anomaly_score": float (0.0 = clean, 1.0 = highly anomalous),
                "signals": [list of detected anomaly signals],
                "risk_level": "LOW" | "MEDIUM" | "HIGH"
            }
        """
        signals = []
        score = 0.0

        # 1. Amount vs. vendor historical average
        hist_signal = self._check_historical_deviation(invoice)
        if hist_signal:
            signals.append(hist_signal)
            score = max(score, hist_signal["weight"])

        # 2. Round number detection
        round_signal = self._check_round_number(invoice.total_amount)
        if round_signal:
            signals.append(round_signal)
            score = max(score, round_signal["weight"])

        # 3. GST rate validation
        gst_signals = self._check_gst_rates(invoice)
        for sig in gst_signals:
            signals.append(sig)
            score = max(score, sig["weight"])

        # 4. Mathematical consistency
        math_signal = self._check_math_consistency(invoice)
        if math_signal:
            signals.append(math_signal)
            score = max(score, math_signal["weight"])

        risk_level = (
            "HIGH" if score >= self.HIGH_ANOMALY_SCORE
            else "MEDIUM" if score >= self.MEDIUM_ANOMALY_SCORE
            else "LOW"
        )

        return {
            "anomaly_score": round(score, 4),
            "signals": signals,
            "risk_level": risk_level,
        }

    def _check_historical_deviation(
        self, invoice: Invoice
    ) -> Optional[Dict[str, Any]]:
        """Check if invoice amount deviates significantly from vendor history."""
        if not invoice.vendor_id:
            return None

        # Get last 20 invoices for this vendor (excluding current)
        historical = (
            self.db.query(Invoice)
            .filter(
                Invoice.vendor_id == invoice.vendor_id,
                Invoice.id != invoice.id,
                Invoice.total_amount > 0,
            )
            .order_by(Invoice.invoice_date.desc())
            .limit(20)
            .all()
        )

        if len(historical) < 3:
            return None  # not enough history

        amounts = [h.total_amount for h in historical]
        mean = sum(amounts) / len(amounts)
        variance = sum((a - mean) ** 2 for a in amounts) / len(amounts)
        std_dev = math.sqrt(variance) if variance > 0 else 0

        if std_dev == 0:
            return None

        z_score = abs(invoice.total_amount - mean) / std_dev

        if z_score >= 3.0:
            return {
                "type": "AMOUNT_STATISTICAL_OUTLIER",
                "description": f"Invoice amount ₹{invoice.total_amount:,.2f} is {z_score:.1f} standard deviations from vendor average ₹{mean:,.2f}",
                "weight": 0.70,
                "details": {"z_score": round(z_score, 2), "vendor_mean": round(mean, 2), "std_dev": round(std_dev, 2)},
            }
        elif z_score >= 2.0:
            return {
                "type": "AMOUNT_HIGH_DEVIATION",
                "description": f"Invoice amount is {z_score:.1f}σ above vendor mean",
                "weight": 0.35,
                "details": {"z_score": round(z_score, 2), "vendor_mean": round(mean, 2)},
            }

        return None

    def _check_round_number(self, amount: float) -> Optional[Dict[str, Any]]:
        """Flag suspiciously round numbers (e.g., exactly ₹1,00,000.00)."""
        if amount <= 0:
            return None
        # Check if amount is a multiple of 1000 and >= 10,000
        if amount >= 10000 and amount % 1000 == 0:
            return {
                "type": "ROUND_NUMBER_AMOUNT",
                "description": f"Invoice total ₹{amount:,.2f} is a suspiciously round number",
                "weight": self.LOW_ANOMALY_SCORE,
                "details": {"amount": amount},
            }
        return None

    def _check_gst_rates(self, invoice: Invoice) -> List[Dict[str, Any]]:
        """Check if invoice items use non-standard GST rates."""
        signals = []
        items = invoice.items if invoice.items else []

        for item in items:
            gst_rate = item.gst_rate or 0.0
            if gst_rate not in STANDARD_GST_RATES_FLOAT:
                signals.append({
                    "type": "NON_STANDARD_GST_RATE",
                    "description": f"Item '{item.description[:40]}' has non-standard GST rate {gst_rate}% (standard: 0, 5, 12, 18, 28)",
                    "weight": 0.40,
                    "details": {"item": item.description, "gst_rate": gst_rate},
                })

        return signals

    def _check_math_consistency(self, invoice: Invoice) -> Optional[Dict[str, Any]]:
        """Verify that item totals sum to invoice subtotal + tax = total."""
        items = invoice.items if invoice.items else []
        if not items:
            return None

        computed_subtotal = sum(item.taxable_value or (item.quantity * item.unit_price) for item in items)
        computed_tax = sum(item.gst_amount or 0.0 for item in items)
        computed_total = computed_subtotal + computed_tax

        declared_total = invoice.total_amount
        tolerance = declared_total * 0.001  # 0.1% tolerance for rounding

        if abs(computed_total - declared_total) > max(tolerance, 1.0):
            return {
                "type": "MATH_INCONSISTENCY",
                "description": (
                    f"Computed total ₹{computed_total:,.2f} does not match "
                    f"declared total ₹{declared_total:,.2f} "
                    f"(difference: ₹{abs(computed_total - declared_total):,.2f})"
                ),
                "weight": 0.65,
                "details": {
                    "computed_total": round(computed_total, 2),
                    "declared_total": declared_total,
                    "difference": round(abs(computed_total - declared_total), 2),
                },
            }

        return None
