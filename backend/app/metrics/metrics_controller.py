from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
from app.auth.auth_service import auth_service
from app.metrics.metrics_service import metrics_service
from app.metrics.metrics_entity import Metric, MetricUpdate

router = APIRouter(prefix="/api/metrics", tags=["metrics"])

@router.get("/establishment/{rbd}", response_model=List[Metric])
async def get_historical_metrics(
    rbd: str,
    current_user: dict = Depends(auth_service.get_current_user)
):
    return await metrics_service.find_by_rbd(rbd)

@router.get("/establishment/{rbd}/{year}", response_model=Metric)
async def get_metric_by_year(
    rbd: str,
    year: int,
    current_user: dict = Depends(auth_service.get_current_user)
):
    metric = await metrics_service.find_by_rbd_and_year(rbd, year)
    if not metric:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Metrics for RBD {rbd} and year {year} not found"
        )
    return metric

@router.put("/establishment/{rbd}/{year}", response_model=Metric)
async def upsert_metric(
    rbd: str,
    year: int,
    payload: MetricUpdate,
    current_user: dict = Depends(auth_service.get_current_user)
):
    return await metrics_service.upsert(rbd, year, payload)
