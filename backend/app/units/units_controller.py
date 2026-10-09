from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.auth_entity import AccessContext, IAM_ADMIN, PLATFORM_IAM
from app.auth.auth_service import require_access
from app.units.units_entity import (Unit, UnitConflict, UnitCreate, UnitHead, UnitMove, UnitNode,
                                    UnitNotFound, UnitStatus, UnitUpdate)
from app.units.units_service import units_service
from app.users.users_service import users_service

router = APIRouter(prefix="/api/units", tags=["units"])

# Leer unidades lo puede hacer cualquier usuario autenticado; escribir, solo el admin global.
_ANY_USER = Depends(require_access(None))
_IAM_ADMIN = Depends(require_access(PLATFORM_IAM, IAM_ADMIN))


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, UnitNotFound):
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(status.HTTP_409_CONFLICT, detail={"code": exc.code, "message": exc.message})


async def _expand_heads(units: List[dict]) -> None:
    """Agrega `head` (solo id y nombre a mostrar) a cada unidad, recorriendo hijos. Es una
    composición de lectura entre dos services en el controller (ADR-013)."""
    flat: List[dict] = []
    stack = list(units)
    while stack:
        u = stack.pop()
        flat.append(u)
        stack.extend(u.get("children", []))
    names = await users_service.display_names([u["head_user_id"] for u in flat if u.get("head_user_id")])
    for u in flat:
        hid = u.get("head_user_id")
        u["head"] = {"id": hid, "display_name": names[hid]} if hid and hid in names else None


@router.get("", response_model=List[Unit])
async def list_units(
    status_filter: Optional[UnitStatus] = Query(None, alias="status"),
    level: Optional[int] = Query(None, ge=1, le=5),
    expand: Optional[str] = Query(None, pattern="^head$"),
    ctx: AccessContext = _ANY_USER,
):
    units = await units_service.find_all(status=status_filter.value if status_filter else None, level=level)
    if expand == "head":
        await _expand_heads(units)
    return units


@router.get("/tree", response_model=List[UnitNode])
async def get_tree(
    status_filter: Optional[UnitStatus] = Query(None, alias="status"),
    expand: Optional[str] = Query(None, pattern="^head$"),
    ctx: AccessContext = _ANY_USER,
):
    tree = await units_service.tree(status=status_filter.value if status_filter else None)
    if expand == "head":
        await _expand_heads(tree)
    return tree


@router.get("/{unit_id}", response_model=Unit)
async def get_unit(unit_id: str, ctx: AccessContext = _ANY_USER):
    unit = await units_service.find_by_id(unit_id)
    if unit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Unit {unit_id} not found")
    return unit


@router.post("", response_model=Unit, status_code=status.HTTP_201_CREATED)
async def create_unit(payload: UnitCreate, ctx: AccessContext = _IAM_ADMIN):
    try:
        return await units_service.create(payload)
    except (UnitNotFound, UnitConflict) as exc:
        raise _http(exc)


@router.patch("/{unit_id}", response_model=Unit)
async def update_unit(unit_id: str, payload: UnitUpdate, ctx: AccessContext = _IAM_ADMIN):
    try:
        return await units_service.update(unit_id, payload)
    except (UnitNotFound, UnitConflict) as exc:
        raise _http(exc)


@router.post("/{unit_id}/move", response_model=Unit)
async def move_unit(unit_id: str, payload: UnitMove, ctx: AccessContext = _IAM_ADMIN):
    try:
        return await units_service.move(unit_id, payload.parent_id)
    except (UnitNotFound, UnitConflict) as exc:
        raise _http(exc)


@router.post("/{unit_id}/deactivate", response_model=Unit)
async def deactivate_unit(unit_id: str, ctx: AccessContext = _IAM_ADMIN):
    # El conteo lo calcula el controller para que `units` no importe `users` (ADR-013).
    active_users = await users_service.count_active_in_unit(unit_id)
    try:
        return await units_service.deactivate(unit_id, active_users)
    except (UnitNotFound, UnitConflict) as exc:
        raise _http(exc)


@router.post("/{unit_id}/activate", response_model=Unit)
async def activate_unit(unit_id: str, ctx: AccessContext = _IAM_ADMIN):
    try:
        return await units_service.activate(unit_id)
    except (UnitNotFound, UnitConflict) as exc:
        raise _http(exc)


@router.put("/{unit_id}/head", response_model=Unit)
async def set_unit_head(unit_id: str, payload: UnitHead, ctx: AccessContext = _IAM_ADMIN):
    candidate = None
    if payload.user_id is not None:
        candidate = await users_service.head_candidate(payload.user_id)
        if candidate is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"User {payload.user_id} not found")
    try:
        return await units_service.set_head(unit_id, candidate)
    except (UnitNotFound, UnitConflict) as exc:
        raise _http(exc)
