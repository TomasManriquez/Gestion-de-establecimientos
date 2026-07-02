from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
from app.auth.auth_service import auth_service
from app.establishments.establishments_service import establishments_service
from app.establishments.establishments_entity import Establishment, EstablishmentUpdate

router = APIRouter(prefix="/api/establishments", tags=["establishments"])

@router.get("", response_model=List[Establishment])
async def get_establishments(
    search: Optional[str] = Query(None, description="Buscar por nombre o RBD"),
    comuna: Optional[str] = Query(None, description="Filtrar por comuna"),
    area_type: Optional[str] = Query(None, description="Filtrar por área (URBANO/RURAL)"),
    category: Optional[str] = Query(None, description="Filtrar por categoría de establecimiento"),
    coverage: Optional[str] = Query(None, description="Filtrar por cobertura curricular"),
    adp: Optional[str] = Query(None, description="Filtrar por cargo ADP (Si/No)"),
    current_user: dict = Depends(auth_service.get_current_user) # Require authentication for reading directory
):
    return await establishments_service.find_all(
        search=search,
        comuna=comuna,
        area_type=area_type,
        category=category,
        coverage=coverage,
        adp=adp
    )

@router.get("/{rbd}", response_model=Establishment)
async def get_establishment_detail(
    rbd: str,
    current_user: dict = Depends(auth_service.get_current_user)
):
    est = await establishments_service.find_by_rbd(rbd)
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
    current_user: dict = Depends(auth_service.get_current_user) # Only logged-in users can update
):
    updated_est = await establishments_service.update_by_rbd(rbd, payload)
    if not updated_est:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not update establishment with RBD {rbd}"
        )
    return updated_est
