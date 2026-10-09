from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.audit.audit_entity import AuditAction, AuditListResponse, AuditTarget
from app.audit.audit_service import audit_service
from app.auth.auth_entity import AccessContext, IAM_ADMIN, PLATFORM_IAM
from app.auth.auth_service import require_access

router = APIRouter(prefix="/api/audit", tags=["audit"])

_IAM_ADMIN = Depends(require_access(PLATFORM_IAM, IAM_ADMIN))


@router.get("", response_model=AuditListResponse)
async def list_audit(
    actor_id: Optional[str] = Query(None, min_length=24, max_length=24, description="Quién hizo el cambio"),
    action: Optional[AuditAction] = Query(None),
    target_type: Optional[AuditTarget] = Query(None),
    target_id: Optional[str] = Query(None, max_length=64),
    bulk_id: Optional[str] = Query(None, max_length=64, description="Todas las filas de una operación masiva"),
    since: Optional[datetime] = Query(None, description="UTC, inclusive"),
    until: Optional[datetime] = Query(None, description="UTC, inclusive"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200, description="Items por página (máx 200)"),
    ctx: AccessContext = _IAM_ADMIN,
):
    """Solo lectura y solo `iam/admin`: no existe ninguna ruta que edite o borre registros."""
    return await audit_service.list_entries(
        actor_id=actor_id, action=action.value if action else None,
        target_type=target_type.value if target_type else None, target_id=target_id, bulk_id=bulk_id,
        since=since.replace(tzinfo=None) if since else None, until=until.replace(tzinfo=None) if until else None,
        page=page, page_size=page_size)
