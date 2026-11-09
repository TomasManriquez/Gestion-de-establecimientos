from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.access.access_service import access_service
from app.auth.auth_entity import AccessContext, IAM_ADMIN, PLATFORM_IAM, RateLimited
from app.auth.auth_service import auth_service, rate_limited_http, require_access
from app.establishments.establishments_service import establishments_service
from app.vault.vault_entity import (Credential, CredentialCreate, CredentialUpdate, REVEAL_LIMIT,
                                    REVEAL_WINDOW_SECONDS, Reveal)
from app.vault.vault_service import VaultError, vault_service

router = APIRouter(prefix="/api/v1/establishments/{rbd}/vault", tags=["vault"])

# Cualquier persona autenticada llega a la ruta; quién ve cada bóveda lo decide `access` (ADR-021).
_AUTHENTICATED = Depends(require_access(None))


async def _authorize(ctx: AccessContext, rbd: str) -> None:
    """403 sin concesión sobre la bóveda de este establecimiento (o `"*"`); `iam/admin` siempre pasa.
    Después, 404 si el establecimiento no existe. El rol de `datos` no abre nada."""
    is_admin = any(a.get("platform_id") == PLATFORM_IAM and a.get("role") in IAM_ADMIN
                   for a in ctx.user.get("access", []))
    if not await access_service.can(ctx.user_id, "vault", rbd, is_iam_admin=is_admin, unit_id=ctx.user.get("unit_id")):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    if await establishments_service.find_by_rbd(rbd) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Establecimiento no encontrado")


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail="Credencial no encontrada")


@router.get("", response_model=List[Credential])
async def list_credentials(rbd: str, ctx: AccessContext = _AUTHENTICATED):
    await _authorize(ctx, rbd)
    return await vault_service.list_for(rbd)


@router.post("", response_model=Credential, status_code=status.HTTP_201_CREATED)
async def create_credential(rbd: str, payload: CredentialCreate, ctx: AccessContext = _AUTHENTICATED):
    await _authorize(ctx, rbd)
    return await vault_service.create(rbd, payload, ctx.user_id)


@router.put("/{cred_id}", response_model=Credential)
async def update_credential(rbd: str, cred_id: str, payload: CredentialUpdate, ctx: AccessContext = _AUTHENTICATED):
    await _authorize(ctx, rbd)
    updated = await vault_service.update(rbd, cred_id, payload, ctx.user_id)
    if updated is None:
        raise _not_found()
    return updated


@router.delete("/{cred_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(rbd: str, cred_id: str, ctx: AccessContext = _AUTHENTICATED):
    await _authorize(ctx, rbd)
    if not await vault_service.delete(rbd, cred_id, ctx.user_id):
        raise _not_found()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{cred_id}/reveal", response_model=Reveal)
async def reveal_credential(rbd: str, cred_id: str, response: Response, ctx: AccessContext = _AUTHENTICATED):
    """Única ruta que devuelve la contraseña. Orden: permiso → límite → registro de auditoría → contar → entrega."""
    await _authorize(ctx, rbd)
    key = auth_service.rate_key("vault_reveal", ctx.user_id)      # por persona, no por IP
    try:
        await auth_service.rate_guard([(key, REVEAL_LIMIT)])
    except RateLimited as exc:
        raise rate_limited_http(exc)
    try:
        password = await vault_service.reveal(rbd, cred_id, ctx.user_id)
    except VaultError as exc:
        if exc.code == "audit_failed":
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                                detail="No se pudo registrar la revelación; la contraseña no se entregó")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No se pudo descifrar la credencial")
    if password is None:
        raise _not_found()
    await auth_service.rate_hit(key, REVEAL_WINDOW_SECONDS)
    response.headers["Cache-Control"] = "no-store"
    return Reveal(password=password)
