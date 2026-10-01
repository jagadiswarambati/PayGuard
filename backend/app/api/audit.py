from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Optional

from ..database import get_db
from ..models import AuditEvent

router = APIRouter(prefix="/api/audit", tags=["audit"])

@router.get("")
async def list_audit_events(
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    action: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List audit events with optional filtering"""
    query = db.query(AuditEvent)
    
    if entity_type:
        query = query.filter(AuditEvent.entity_type == entity_type)
    if entity_id is not None:
        query = query.filter(AuditEvent.entity_id == entity_id)
    if action:
        query = query.filter(AuditEvent.action == action)
    
    events = query.order_by(AuditEvent.timestamp.desc()).offset(skip).limit(limit).all()
    
    return [
        {
            "id": event.id,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "action": event.action.value,
            "actor_type": event.actor_type.value,
            "actor_id": event.actor_id,
            "result": event.result,
            "metadata": event.event_metadata or {},
            "timestamp": event.timestamp.isoformat()
        }
        for event in events
    ]
