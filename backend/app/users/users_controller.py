import logging
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Response, UploadFile, status

from app.auth.auth_entity import AccessContext, IAM_ADMIN, PLATFORM_IAM
from app.auth.auth_entity import INVITE_BATCH_LIMIT, RateLimited, SEND_ACTOR_LIMIT, SEND_TARGET_LIMIT, SEND_WINDOW_SECONDS
from app.auth.auth_service import auth_service, rate_limited_http, require_access
from app.mail.mail_service import MailError
from app.users.users_entity import (AccessGrant, BulkCreateRequest, BulkRequest, BulkResult, CSV_COLUMNS,
                                    EstablishmentPosition, ImportPreview, MAX_CSV_BYTES, User, UserAdminUpdate,
                                    UserConflict, UserCreate, UserInvalid, UserListResponse, UserMe,
                                    UserNotFound, UserSelfUpdate, UserStatus)
from app.units.units_service import units_service
from app.users.users_service import users_service

router = APIRouter(prefix="/api/users", tags=["users"])

logger = logging.getLogger("users")

# Todo `/api/users/*` es del admin global, salvo `/me` (cualquier usuario autenticado).
_ANY_USER = Depends(require_access(None))
_IAM_ADMIN = Depends(require_access(PLATFORM_IAM, IAM_ADMIN))


async def _guard_send(actor_id: str, target_id: str) -> None:
    """Reenvío y restablecimiento: tope por destinatario (su bandeja) y por administrador (ADR-014).
    Cada intento cuenta, haya salido el correo o no."""
    target_key = auth_service.rate_key("send-target", target_id)
    actor_key = auth_service.rate_key("send-actor", actor_id)
    try:
        await auth_service.rate_guard([(target_key, SEND_TARGET_LIMIT), (actor_key, SEND_ACTOR_LIMIT)])
    except RateLimited as exc:
        raise rate_limited_http(exc)
    await auth_service.rate_hit(target_key, SEND_WINDOW_SECONDS)
    await auth_service.rate_hit(actor_key, SEND_WINDOW_SECONDS)


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, UserNotFound):
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, UserConflict):
        return HTTPException(status.HTTP_409_CONFLICT,
                             detail={"code": exc.code, "message": exc.message, "field": exc.field})
    return HTTPException(422, detail=exc.errors)


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
    acting: bool = Query(False, description="Solo quienes subrogan una jefatura hoy"),
    assignment: Optional[str] = Query(None, pattern="^unassigned$", description="unassigned: cuentas sin asignar (alta automática)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200, description="Items por página (máx 200)"),
    ctx: AccessContext = _IAM_ADMIN,
):
    acting_ids = await units_service.acting_user_ids() if acting else None
    return await users_service.list_users(
        q=q, unit_id=unit_id, include_descendants=include_descendants, level=level, kind=kind,
        rbd=rbd, position=position.value if position else None, platform=platform, role=role,
        status=status_filter.value if status_filter else None, only_ids=acting_ids, assignment=assignment,
        page=page, page_size=page_size)


@router.post("", response_model=User, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, ctx: AccessContext = _IAM_ADMIN):
    """Alta individual: es `create_many([item])`, la misma ruta que usarán el CSV y el seed (R6)."""
    try:
        created = await users_service.create(payload.model_dump(mode="json"), ctx.user_id)
    except (UserConflict, UserInvalid) as exc:
        raise _http(exc)
    # La invitación sale después del alta y un fallo de correo no la revierte (ADR-012): el usuario
    # queda `invited` y `invitation.last_error` dice por qué. La respuesta ya refleja el resultado.
    await auth_service.send_invitation(created, ctx.user_id)
    return await users_service.find_by_id(created["_id"])


async def _invite_created(user_ids: List[str], actor_id: str, bulk_id: str) -> None:
    """Invitaciones de un alta masiva: salen DESPUÉS de responder (BackgroundTasks, que corre en el
    proceso y no es una cola) y en serie, en lotes de INVITE_BATCH_LIMIT por la cuota de Gmail."""
    try:
        for start in range(0, len(user_ids), INVITE_BATCH_LIMIT):
            users = await users_service.find_many(user_ids[start:start + INVITE_BATCH_LIMIT])
            await auth_service.invite_many(users, actor_id, bulk_id)
    except Exception:  # noqa: BLE001 — el alta ya está hecha; el motivo queda en el log
        logger.exception("Falló el envío en segundo plano de las invitaciones (bulk_id=%s)", bulk_id)


@router.get("/import/template")
async def import_template(ctx: AccessContext = _IAM_ADMIN):
    """Plantilla CSV generada por el servidor (no es un archivo versionado). UTF-8 con BOM y `;`,
    que es lo que abre bien Excel en español."""
    sample = [
        ["ana.perez@slepllanquihue.cl", "Ana", "Pérez", "+56912345678", "4521", "AF-TI", "", ""],
        ["luis.soto@slepllanquihue.cl", "Luis", "Soto", "", "", "", "7722", "DOCENTE|PIE_ENCARGADO"],
    ]
    lines = [";".join(CSV_COLUMNS)] + [";".join(r) for r in sample]
    body = "\ufeff" + "\r\n".join(lines) + "\r\n"
    return Response(content=body.encode("utf-8"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="plantilla-usuarios.csv"'})


@router.post("/import", response_model=ImportPreview)
async def import_users(file: UploadFile = File(...), ctx: AccessContext = _IAM_ADMIN):
    """CSV → JSON con vista previa. NO escribe: cada fila trae su `data` (un ítem de `bulk-create`)
    y sus `errors`. Máximo 1 MiB y 200 filas."""
    raw = await file.read(MAX_CSV_BYTES + 1)
    if len(raw) > MAX_CSV_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail={
            "code": "file_too_large", "message": f"El archivo supera {MAX_CSV_BYTES // 1024} KiB"})
    try:
        return await users_service.preview_import(raw, ctx.user_id)
    except UserInvalid as exc:
        raise _http(exc)


@router.post("/bulk-create", response_model=BulkResult)
async def bulk_create_users(payload: BulkCreateRequest, background: BackgroundTasks, ctx: AccessContext = _IAM_ADMIN):
    """Alta masiva PARCIAL: los ítems inválidos o repetidos se informan por fila y no frenan al resto.
    Con `dry_run` valida todo y no escribe ni envía nada. Las invitaciones salen después de responder."""
    result = await users_service.create_many(payload.items, ctx.user_id, dry_run=payload.dry_run)
    created = [r["id"] for r in result["items"] if r["status"] == "created"]
    for row in result["items"]:
        if row["status"] == "created":
            row["invitation"] = "queued"
    if created:
        background.add_task(_invite_created, created, ctx.user_id, result["bulk_id"])
    return result


@router.post("/bulk", response_model=BulkResult)
async def bulk_users(payload: BulkRequest, ctx: AccessContext = _IAM_ADMIN):
    """Una operación (`assign_unit`, `grant_access`, `revoke_access`, `disable`, `enable`) sobre hasta 200
    usuarios. Resultado por usuario; las invariantes de admin se aplican a medida que avanza el lote."""
    try:
        return await users_service.bulk(payload, ctx.user_id)
    except (UserNotFound, UserInvalid) as exc:
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


@router.post("/{user_id}/invitation", response_model=User)
async def resend_invitation(user_id: str, ctx: AccessContext = _IAM_ADMIN):
    """Reenvío: emite un token nuevo (invalida el anterior). Solo a usuarios `invited`. Si el correo
    falla responde 200 con el usuario y `invitation.last_error`: el documento dice la verdad."""
    user = await users_service.find_by_id(user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"User {user_id} not found")
    if user["status"] != "invited":
        raise _http(UserConflict("Solo se puede reenviar la invitación a un usuario invitado", "not_invited"))
    await _guard_send(ctx.user_id, user_id)
    await auth_service.send_invitation(user, ctx.user_id)
    return await users_service.find_by_id(user_id)


@router.post("/{user_id}/password-reset", status_code=status.HTTP_202_ACCEPTED)
async def request_password_reset(user_id: str, ctx: AccessContext = _IAM_ADMIN):
    """El admin nunca ve ni define la contraseña: la persona recibe un enlace de un solo uso (24 h).
    Solo `active`. Si el correo no sale, 502: aquí el correo es la operación."""
    user = await users_service.find_by_id(user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"User {user_id} not found")
    if user["status"] != "active":
        raise _http(UserConflict("Solo se puede restablecer la contraseña de un usuario activo", "not_active"))
    await _guard_send(ctx.user_id, user_id)
    try:
        expires = await auth_service.send_password_reset(user, ctx.user_id)
    except MailError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail={
            "code": exc.code, "message": "No se pudo enviar el correo. Inténtalo de nuevo o revisa la configuración del envío."})
    return {"sent": True, "expires_at": expires}
