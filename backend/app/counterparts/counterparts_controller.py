from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.auth.auth_service import require_access
from app.auth.auth_entity import (AccessContext, PLATFORM_DATOS, DATOS_READ, DATOS_WRITE,
                                  DATOS_DELETE, SENSITIVE_ROLES)
from app.counterparts.counterparts_service import counterparts_service
from app.counterparts.counterparts_entity import Counterpart, CounterpartCreate, CounterpartUpdate

router = APIRouter(prefix="/api/counterparts", tags=["counterparts"])

@router.get("/establishment/{rbd}", response_model=List[Counterpart])
async def get_counterparts_by_establishment(
    rbd: str,
    ctx: AccessContext = Depends(require_access(PLATFORM_DATOS, DATOS_READ))
):
    return await counterparts_service.find_by_rbd(rbd)

@router.post("", response_model=Counterpart, status_code=status.HTTP_201_CREATED)
async def create_counterpart(
    payload: CounterpartCreate,
    ctx: AccessContext = Depends(require_access(PLATFORM_DATOS, DATOS_WRITE))
):
    return await counterparts_service.create(payload)

@router.put("/{cp_id}", response_model=Counterpart)
async def update_counterpart(
    cp_id: str,
    payload: CounterpartUpdate,
    ctx: AccessContext = Depends(require_access(PLATFORM_DATOS, DATOS_WRITE))
):
    updated = await counterparts_service.update(cp_id, payload)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Counterpart with ID {cp_id} not found"
        )
    return updated

@router.delete("/{cp_id}", status_code=status.HTTP_200_OK)
async def delete_counterpart(
    cp_id: str,
    ctx: AccessContext = Depends(require_access(PLATFORM_DATOS, DATOS_DELETE))
):
    success = await counterparts_service.delete(cp_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Counterpart with ID {cp_id} not found"
        )
    return {"message": "Counterpart deleted successfully"}
