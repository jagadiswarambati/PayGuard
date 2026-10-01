from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from ..database import get_db
from ..models import AuditEvent, AuditAction, ActorType
from ..services.settings_service import get_all_settings, update_system_setting

router = APIRouter(prefix="/api/settings", tags=["settings"])

class SettingsUpdate(BaseModel):
    po_price_tolerance: Optional[float] = Field(None, ge=0.0, le=1.0)
    po_quantity_tolerance: Optional[float] = Field(None, ge=0.0, le=1.0)
    approval_threshold_low: Optional[float] = Field(None, ge=0.0)
    approval_threshold_medium: Optional[float] = Field(None, ge=0.0)
    auto_approval_enabled: Optional[bool] = None

@router.get("")
async def get_settings_endpoint(db: Session = Depends(get_db)):
    """Retrieve current system tolerances and approval routing thresholds"""
    return get_all_settings(db)

@router.put("")
async def update_settings_endpoint(
    data: SettingsUpdate,
    db: Session = Depends(get_db)
):
    """Update system tolerances and approval routing thresholds"""
    updated = {}
    
    if data.po_price_tolerance is not None:
        update_system_setting(db, "po_price_tolerance", str(data.po_price_tolerance), "Purchase order price variance tolerance")
        updated["po_price_tolerance"] = data.po_price_tolerance
        
    if data.po_quantity_tolerance is not None:
        update_system_setting(db, "po_quantity_tolerance", str(data.po_quantity_tolerance), "Purchase order quantity variance tolerance")
        updated["po_quantity_tolerance"] = data.po_quantity_tolerance
        
    if data.approval_threshold_low is not None:
        update_system_setting(db, "approval_threshold_low", str(data.approval_threshold_low), "Threshold for automatic approval")
        updated["approval_threshold_low"] = data.approval_threshold_low
        
    if data.approval_threshold_medium is not None:
        update_system_setting(db, "approval_threshold_medium", str(data.approval_threshold_medium), "Threshold for senior finance dual approval")
        updated["approval_threshold_medium"] = data.approval_threshold_medium

    if data.auto_approval_enabled is not None:
        update_system_setting(db, "auto_approval_enabled", str(data.auto_approval_enabled).lower(), "Enable automatic approval below low threshold")
        updated["auto_approval_enabled"] = data.auto_approval_enabled

    audit = AuditEvent(
        entity_type="SystemSetting",
        entity_id=0,
        action=AuditAction.SETTINGS_UPDATED,
        actor_type=ActorType.USER,
        result="UPDATED",
        event_metadata=updated
    )
    db.add(audit)
    db.commit()

    return {"status": "success", "settings": get_all_settings(db)}
