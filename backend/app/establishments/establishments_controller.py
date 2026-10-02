from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
from app.auth.auth_service import require_access
from app.auth.auth_entity import (AccessContext, PLATFORM_DATOS, DATOS_READ, DATOS_WRITE,
                                  DATOS_DELETE, SENSITIVE_ROLES)
from app.establishments.establishments_service import establishments_service
from app.establishments.establishments_entity import (
    Establishment, EstablishmentUpdate,
    EstablishmentSummary, EstablishmentListResponse, RedactedPlaceholderError
)

router = APIRouter(prefix="/api/establishments", tags=["establishments"])

@router.get("", response_model=EstablishmentListResponse)
async def get_establishments(
    search: Optional[str] = Query(None, description="Buscar por nombre o RBD"),
    comuna: Optional[str] = Query(None, description="Filtrar por comuna"),
    area_type: Optional[str] = Query(None, description="Filtrar por área (URBANO/RURAL)"),
    category: Optional[str] = Query(None, description="Filtrar por categoría de establecimiento"),
    coverage: Optional[str] = Query(None, description="Filtrar por cobertura curricular"),
    adp: Optional[str] = Query(None, description="Filtrar por cargo ADP (Si/No)"),
    page: int = Query(1, ge=1, description="Página actual"),
    page_size: int = Query(100, ge=1, le=200, description="Items por página (máx 200)"),
    ctx: AccessContext = Depends(require_access(PLATFORM_DATOS, DATOS_READ)),
):
    return await establishments_service.find_all(
        search=search,
        comuna=comuna,
        area_type=area_type,
        category=category,
        coverage=coverage,
        adp=adp,
        page=page,
        page_size=page_size
    )

@router.get("/{rbd}", response_model=Establishment)
async def get_establishment_detail(
    rbd: str,
    ctx: AccessContext = Depends(require_access(PLATFORM_DATOS, DATOS_READ)),
):
    # Solo `viewer` recibe las credenciales redactadas (C20). El service no sabe qué es un rol.
    include_sensitive = ctx.role in SENSITIVE_ROLES
    est = await establishments_service.find_by_rbd(rbd, include_sensitive=include_sensitive)
    if not est:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Establishment with RBD {rbd} not found"
        )
    return est

@router.put("/{rbd}", response_model=Establishment)
async def update_establishment(
    rbd: str,
    payload: EstablishmentUpdate,
    ctx: AccessContext = Depends(require_access(PLATFORM_DATOS, DATOS_WRITE)),
):
    try:
        updated_est = await establishments_service.update_by_rbd(
            rbd, payload, include_sensitive=ctx.role in SENSITIVE_ROLES)
    except RedactedPlaceholderError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if not updated_est:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not update establishment with RBD {rbd}"
        )
    return updated_est
