from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.access.access_entity import Grant, GrantCreate, ResourceType
from app.access.access_service import GrantError, access_service
from app.auth.auth_entity import AccessContext, IAM_ADMIN, PLATFORM_IAM
from app.auth.auth_service import require_access

# Primer router bajo /api/v1 (D10). Solo `iam/admin` concede y revoca (ADR-021).
router = APIRouter(prefix="/api/v1/access/grants", tags=["access"])
_IAM_ADMIN = Depends(require_access(PLATFORM_IAM, IAM_ADMIN))

_ERRORS = {"user_not_found": (status.HTTP_404_NOT_FOUND, "La persona no existe"),
           "user_not_active": (status.HTTP_422_UNPROCESSABLE_ENTITY, "La cuenta no está activa"),
           "unit_not_found": (status.HTTP_404_NOT_FOUND, "La unidad no existe"),
           "unit_not_active": (status.HTTP_422_UNPROCESSABLE_ENTITY, "La unidad no está activa"),
           "already_granted": (status.HTTP_409_CONFLICT, "Ya existe esa concesión")}


@router.get("", response_model=List[Grant])
async def list_grants(resource_type: Optional[ResourceType] = None, resource_id: Optional[str] = None,
                      user_id: Optional[str] = None, ctx: AccessContext = _IAM_ADMIN):
    return await access_service.list_grants(resource_type, resource_id, user_id)


@router.post("", response_model=Grant, status_code=status.HTTP_201_CREATED)
async def create_grant(payload: GrantCreate, ctx: AccessContext = _IAM_ADMIN):
    try:
        return await access_service.create(payload, ctx.user_id)
    except GrantError as exc:
        code, detail = _ERRORS[exc.code]
        raise HTTPException(code, detail=detail)


@router.delete("/{grant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_grant(grant_id: str, ctx: AccessContext = _IAM_ADMIN):
    if not await access_service.revoke(grant_id, ctx.user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Concesión no encontrada")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
