from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from typing import Annotated, List, Optional
from app.auth.auth_service import require_access
from app.auth.auth_entity import (AccessContext, PLATFORM_DATOS, DATOS_READ, DATOS_WRITE,
                                  DATOS_DELETE, SENSITIVE_ROLES)
from app.metrics.metrics_service import metrics_service
from app.metrics.metrics_entity import Metric, MetricUpdate

router = APIRouter(prefix="/api/metrics", tags=["metrics"])

@router.get("/establishment/{rbd}", response_model=List[Metric])
async def get_historical_metrics(
    rbd: str,
    ctx: AccessContext = Depends(require_access(PLATFORM_DATOS, DATOS_READ))
):
    return await metrics_service.find_by_rbd(rbd)

@router.get("/establishment/{rbd}/{year}", response_model=Metric)
async def get_metric_by_year(
    rbd: str,
    year: int,
    ctx: AccessContext = Depends(require_access(PLATFORM_DATOS, DATOS_READ))
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
    year: Annotated[int, Path(ge=2000, le=2100)],
    payload: MetricUpdate,
    ctx: AccessContext = Depends(require_access(PLATFORM_DATOS, DATOS_WRITE))
):
    metric = await metrics_service.upsert(rbd, year, payload)
    if metric is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Establishment {rbd} not found")
    return metric
