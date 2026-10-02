from fastapi import APIRouter, Depends
from app.auth.auth_service import require_access
from app.auth.auth_entity import (AccessContext, PLATFORM_DATOS, DATOS_READ, DATOS_WRITE,
                                  DATOS_DELETE, SENSITIVE_ROLES)
from app.analytics.analytics_service import analytics_service

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

@router.get("/kpis")
async def get_kpis(ctx: AccessContext = Depends(require_access(PLATFORM_DATOS, DATOS_READ))):
    return await analytics_service.get_kpis()

@router.get("/charts")
async def get_charts_data(ctx: AccessContext = Depends(require_access(PLATFORM_DATOS, DATOS_READ))):
    return await analytics_service.get_charts_data()
