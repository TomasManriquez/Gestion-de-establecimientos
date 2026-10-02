from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.auth_entity import AccessContext, IAM_ADMIN, PLATFORM_IAM
from app.auth.auth_service import require_access
from app.users.users_entity import (AccessGrant, EstablishmentPosition, User, UserAdminUpdate,
                                    UserConflict, UserCreate, UserInvalid, UserListResponse, UserMe,
                                    UserNotFound, UserSelfUpdate, UserStatus)
from app.users.users_service import users_service

router = APIRouter(prefix="/api/users", tags=["users"])

# Todo `/api/users/*` es del admin global, salvo `/me` (cualquier usuario autenticado).
_ANY_USER = Depends(require_access(None))
_IAM_ADMIN = Depends(require_access(PLATFORM_IAM, IAM_ADMIN))


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, UserNotFound):
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, UserConflict):
        return HTTPException(status.HTTP_409_CONFLICT,
                             detail={"code": exc.code, "message": exc.message, "field": exc.field})
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors)


# Las rutas fijas (/me) van ANTES que /{user_id} para que no las capture como un id.

@router.get("/me", response_model=UserMe)
async def get_me(ctx: AccessContext = _ANY_USER):
    return ctx.user


@router.patch("/me", response_model=UserMe)
async def update_me(payload: UserSelfUpdate, ctx: AccessContext = _ANY_USER):
    """C19: solo teléfono y anexo. Cualquier otro campo da 422 por el tipo del body."""
    try:
        return await users_service.update_self(ctx.user_id, payload)
    except UserNotFound as exc:
        raise _http(exc)


@router.get("", response_model=UserListResponse)
async def list_users(
    q: Optional[str] = Query(None, max_length=100, description="Nombre, apellido o correo (texto literal)"),
    unit_id: Optional[str] = Query(None, min_length=24, max_length=24),
    include_descendants: bool = Query(False, description="Con unit_id: incluir el subárbol de la unidad"),
    level: Optional[int] = Query(None, ge=1, le=5, description="Nivel de la unidad del usuario"),
    kind: Optional[str] = Query(None, pattern="^(slep|establishment)$"),
    rbd: Optional[str] = Query(None, pattern="^[0-9]{1,8}$"),
    position: Optional[EstablishmentPosition] = Query(None),
    platform: Optional[str] = Query(None, max_length=30),
    role: Optional[str] = Query(None, max_length=20),
    status_filter: Optional[UserStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200, description="Items por página (máx 200)"),
    ctx: AccessContext = _IAM_ADMIN,
):
    return await users_service.list_users(
        q=q, unit_id=unit_id, include_descendants=include_descendants, level=level, kind=kind,
        rbd=rbd, position=position.value if position else None, platform=platform, role=role,
        status=status_filter.value if status_filter else None, page=page, page_size=page_size)


@router.post("", response_model=User, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, ctx: AccessContext = _IAM_ADMIN):
    """Alta individual: es `create_many([item])`, la misma ruta que usarán el CSV y el seed (R6)."""
    try:
        return await users_service.create(payload.model_dump(mode="json"), ctx.user_id)
    except (UserConflict, UserInvalid) as exc:
        raise _http(exc)


@router.get("/{user_id}", response_model=User)
async def get_user(user_id: str, ctx: AccessContext = _IAM_ADMIN):
    user = await users_service.find_by_id(user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"User {user_id} not found")
    return user


@router.patch("/{user_id}", response_model=User)
async def update_user(user_id: str, payload: UserAdminUpdate, ctx: AccessContext = _IAM_ADMIN):
    try:
        return await users_service.update(user_id, payload, ctx.user_id)
    except (UserNotFound, UserConflict, UserInvalid) as exc:
        raise _http(exc)


@router.post("/{user_id}/disable", response_model=User)
async def disable_user(user_id: str, ctx: AccessContext = _IAM_ADMIN):
    try:
        return await users_service.disable(user_id, ctx.user_id)
    except (UserNotFound, UserConflict) as exc:
        raise _http(exc)


@router.post("/{user_id}/enable", response_model=User)
async def enable_user(user_id: str, ctx: AccessContext = _IAM_ADMIN):
    try:
        return await users_service.enable(user_id, ctx.user_id)
    except (UserNotFound, UserConflict) as exc:
        raise _http(exc)


@router.put("/{user_id}/access/{platform_id}", response_model=User)
async def grant_access(user_id: str, platform_id: str, payload: AccessGrant, ctx: AccessContext = _IAM_ADMIN):
    try:
        return await users_service.set_access(user_id, platform_id, payload.role, ctx.user_id)
    except (UserNotFound, UserConflict, UserInvalid) as exc:
        raise _http(exc)


@router.delete("/{user_id}/access/{platform_id}", response_model=User)
async def revoke_access(user_id: str, platform_id: str, ctx: AccessContext = _IAM_ADMIN):
    try:
        return await users_service.revoke_access(user_id, platform_id, ctx.user_id)
    except (UserNotFound, UserConflict) as exc:
        raise _http(exc)
