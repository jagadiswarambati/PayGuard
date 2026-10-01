"""
PayGuard Intelligence Layer — Entity Resolution
================================================
Resolves vendor identity from raw invoice data using:
  1. Exact GSTIN match
  2. Exact name match
  3. Fuzzy name similarity (difflib SequenceMatcher)

Produces: confidence score + evidence — does NOT approve/reject.
The deterministic ControlEngine uses this evidence to verify.
"""

import difflib
import re
import logging
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from ...models import Vendor

logger = logging.getLogger("payguard.intelligence.entity_resolution")


class EntityResolutionService:
    """
    Resolves raw vendor names/GSTINs from invoice data against the vendor master.
    Returns candidate matches with confidence scores.
    """

    EXACT_MATCH_CONFIDENCE = 1.0
    GSTIN_MATCH_CONFIDENCE = 0.98
    HIGH_SIMILARITY_THRESHOLD = 0.85
    MEDIUM_SIMILARITY_THRESHOLD = 0.70

    def __init__(self, db: Session):
        self.db = db

    def resolve_vendor(
        self,
        raw_name: str,
        raw_gstin: Optional[str] = None,
        raw_pan: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Attempt to resolve a raw vendor name/GSTIN to a registered vendor.

        Returns:
            {
                "resolved": bool,
                "vendor_id": int | None,
                "vendor_name": str | None,
                "method": str,       # "EXACT_GSTIN" | "EXACT_NAME" | "FUZZY_NAME" | "NONE"
                "confidence": float,
                "candidates": [...]  # top alternatives if not exact
            }
        """
        all_vendors = self.db.query(Vendor).all()

        if not all_vendors:
            return self._no_match("No vendors in database")

        # 1. Exact GSTIN match (highest confidence)
        if raw_gstin and len(raw_gstin.strip()) >= 15:
            gstin_clean = raw_gstin.strip().upper()
            for vendor in all_vendors:
                if vendor.gstin and vendor.gstin.upper() == gstin_clean:
                    logger.info(f"Entity resolution: EXACT_GSTIN match → {vendor.name}")
                    return {
                        "resolved": True,
                        "vendor_id": vendor.id,
                        "vendor_name": vendor.name,
                        "method": "EXACT_GSTIN",
                        "confidence": self.GSTIN_MATCH_CONFIDENCE,
                        "candidates": [],
                    }

        # 2. Exact name match (case-insensitive)
        raw_name_clean = raw_name.strip().lower()
        for vendor in all_vendors:
            if vendor.name.strip().lower() == raw_name_clean:
                logger.info(f"Entity resolution: EXACT_NAME match → {vendor.name}")
                return {
                    "resolved": True,
                    "vendor_id": vendor.id,
                    "vendor_name": vendor.name,
                    "method": "EXACT_NAME",
                    "confidence": self.EXACT_MATCH_CONFIDENCE,
                    "candidates": [],
                }

        # 3. Fuzzy name similarity
        scored: List[Tuple[float, Vendor]] = []
        for vendor in all_vendors:
            ratio = difflib.SequenceMatcher(
                None,
                self._normalize_name(raw_name),
                self._normalize_name(vendor.name),
            ).ratio()
            scored.append((ratio, vendor))

        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best_vendor = scored[0] if scored else (0.0, None)

        candidates = [
            {
                "vendor_id": v.id,
                "vendor_name": v.name,
                "confidence": round(s, 4),
            }
            for s, v in scored[:3]
        ]

        if best_score >= self.HIGH_SIMILARITY_THRESHOLD and best_vendor:
            logger.info(
                f"Entity resolution: FUZZY_NAME match ({best_score:.2f}) → {best_vendor.name}"
            )
            return {
                "resolved": True,
                "vendor_id": best_vendor.id,
                "vendor_name": best_vendor.name,
                "method": "FUZZY_NAME",
                "confidence": round(best_score, 4),
                "candidates": candidates,
            }

        # No confident match
        logger.warning(
            f"Entity resolution: no match for '{raw_name}' (best similarity: {best_score:.2f})"
        )
        return {
            "resolved": False,
            "vendor_id": None,
            "vendor_name": raw_name,
            "method": "NONE",
            "confidence": round(best_score, 4),
            "candidates": candidates,
        }

    def _normalize_name(self, name: str) -> str:
        """Normalize vendor name for fuzzy comparison."""
        name = name.lower().strip()
        # Remove common legal suffixes for better matching
        for suffix in [
            " pvt ltd", " private limited", " limited", " ltd",
            " llp", " lp", " inc", " corp", " co.", " & co"
        ]:
            name = name.replace(suffix, "")
        # Remove extra whitespace and punctuation
        name = re.sub(r"[^\w\s]", " ", name)
        name = re.sub(r"\s+", " ", name).strip()
        return name

    def _no_match(self, reason: str) -> Dict[str, Any]:
        return {
            "resolved": False,
            "vendor_id": None,
            "vendor_name": None,
            "method": "NONE",
            "confidence": 0.0,
            "candidates": [],
            "reason": reason,
        }
