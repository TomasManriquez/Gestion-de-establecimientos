from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.auth_entity import AccessContext, IAM_ADMIN, PLATFORM_IAM
from app.auth.auth_service import require_access
from app.platforms.platforms_entity import Platform, PlatformUpdate
from app.platforms.platforms_service import platforms_service

router = APIRouter(prefix="/api/platforms", tags=["platforms"])


@router.get("", response_model=List[Platform])
async def list_platforms(ctx: AccessContext = Depends(require_access(PLATFORM_IAM, IAM_ADMIN))):
    return await platforms_service.find_all()


@router.patch("/{platform_id}", response_model=Platform)
async def update_platform(platform_id: str, payload: PlatformUpdate,
                          ctx: AccessContext = Depends(require_access(PLATFORM_IAM, IAM_ADMIN))):
    updated = await platforms_service.update(platform_id, payload)
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Platform {platform_id} not found")
    return updated
