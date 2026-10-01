from typing import Dict, Any
from sqlalchemy.orm import Session
from ..models.setting import SystemSetting
from ..config import get_settings

config = get_settings()

DEFAULT_SETTINGS = {
    "po_price_tolerance": str(config.po_price_tolerance),
    "po_quantity_tolerance": str(config.po_quantity_tolerance),
    "approval_threshold_low": str(config.approval_threshold_low),
    "approval_threshold_medium": str(config.approval_threshold_medium),
    "auto_approval_enabled": "true",
    "currency_default": "USD",
}

def get_system_setting(db: Session, key: str, default: str = "") -> str:
    setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if setting:
        return setting.value
    if key in DEFAULT_SETTINGS:
        return DEFAULT_SETTINGS[key]
    return default

def get_all_settings(db: Session) -> Dict[str, Any]:
    stored = {s.key: s.value for s in db.query(SystemSetting).all()}
    result = {}
    for k, v in DEFAULT_SETTINGS.items():
        val = stored.get(k, v)
        if k in ("po_price_tolerance", "po_quantity_tolerance", "approval_threshold_low", "approval_threshold_medium"):
            try:
                result[k] = float(val)
            except ValueError:
                result[k] = float(DEFAULT_SETTINGS[k])
        elif k == "auto_approval_enabled":
            result[k] = val.lower() in ("true", "1", "yes")
        else:
            result[k] = val
    return result

def update_system_setting(db: Session, key: str, value: str, description: str = None) -> SystemSetting:
    setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if not setting:
        setting = SystemSetting(key=key, value=str(value), description=description)
        db.add(setting)
    else:
        setting.value = str(value)
        if description:
            setting.description = description
    db.commit()
    db.refresh(setting)
    return setting
