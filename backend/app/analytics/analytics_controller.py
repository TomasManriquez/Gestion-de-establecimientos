from fastapi import APIRouter, Depends
from app.auth.auth_service import auth_service
from app.analytics.analytics_service import analytics_service

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

@router.get("/kpis")
async def get_kpis(current_user: dict = Depends(auth_service.get_current_user)):
    return await analytics_service.get_kpis()

@router.get("/charts")
async def get_charts_data(current_user: dict = Depends(auth_service.get_current_user)):
    return await analytics_service.get_charts_data()
