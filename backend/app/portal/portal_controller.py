from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.access.access_service import access_service
from app.auth.auth_entity import AccessContext, DATOS_READ, DATOS_WRITE, IAM_ADMIN, PLATFORM_DATOS, PLATFORM_IAM
from app.auth.auth_service import require_access
from app.portal.portal_entity import (Resource, ResourceCreate, ResourceUpdate, Topic, TopicCreate, TopicUpdate)
from app.portal.portal_service import RESOURCE_TYPE, PortalError, portal_service

router = APIRouter(prefix="/api/v1/portal", tags=["portal"])
_READ = Depends(require_access(PLATFORM_DATOS, DATOS_READ))
_WRITE = Depends(require_access(PLATFORM_DATOS, DATOS_WRITE))
_ADMIN = Depends(require_access(PLATFORM_IAM, IAM_ADMIN))

_ERRORS = {"parent_not_found": (status.HTTP_404_NOT_FOUND, "El tema padre no existe"),
           "topic_too_deep": (status.HTTP_422_UNPROCESSABLE_ENTITY, "Los temas tienen como máximo dos niveles"),
           "topic_in_use": (status.HTTP_409_CONFLICT, "El tema tiene subtemas o recursos; muévelos antes de borrarlo"),
           "topic_not_found": (status.HTTP_422_UNPROCESSABLE_ENTITY, "El tema no existe"),
           "unit_not_found": (status.HTTP_422_UNPROCESSABLE_ENTITY, "La unidad no existe")}


def _fail(exc: PortalError) -> HTTPException:
    code, detail = _ERRORS[exc.code]
    return HTTPException(code, detail=detail)


def _is_admin(ctx: AccessContext) -> bool:
    return any(a.get("platform_id") == PLATFORM_IAM and a.get("role") in IAM_ADMIN for a in ctx.user.get("access", []))


async def _visible_or_404(ctx: AccessContext, resource_id: str) -> dict:
    """Un recurso que la persona no puede ver responde 404, igual que uno inexistente: no revela que existe."""
    doc = await portal_service.find_resource(resource_id)
    if doc is None or (doc["visibility"] != "org" and not await access_service.can(
            ctx.user_id, RESOURCE_TYPE, resource_id, is_iam_admin=_is_admin(ctx))):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Recurso no encontrado")
    return doc


# ---- temas ----------------------------------------------------------------------------------------------
@router.get("/topics", response_model=List[Topic])
async def list_topics(ctx: AccessContext = _READ):
    return await portal_service.list_topics()


@router.post("/topics", response_model=Topic, status_code=status.HTTP_201_CREATED)
async def create_topic(payload: TopicCreate, ctx: AccessContext = _ADMIN):
    try:
        return await portal_service.create_topic(payload, ctx.user_id)
    except PortalError as exc:
        raise _fail(exc)


@router.put("/topics/{topic_id}", response_model=Topic)
async def rename_topic(topic_id: str, payload: TopicUpdate, ctx: AccessContext = _ADMIN):
    updated = await portal_service.rename_topic(topic_id, payload.name, ctx.user_id)
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tema no encontrado")
    return updated


@router.delete("/topics/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_topic(topic_id: str, ctx: AccessContext = _ADMIN):
    try:
        found = await portal_service.delete_topic(topic_id, ctx.user_id)
    except PortalError as exc:
        raise _fail(exc)
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tema no encontrado")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- recursos -------------------------------------------------------------------------------------------
@router.get("/resources", response_model=List[Resource])
async def list_resources(topic_id: Optional[str] = None, ctx: AccessContext = _READ):
    visible = await access_service.visible_ids(ctx.user_id, RESOURCE_TYPE, is_iam_admin=_is_admin(ctx))
    return await portal_service.list_resources(visible, topic_id)


@router.get("/resources/{resource_id}", response_model=Resource)
async def get_resource(resource_id: str, ctx: AccessContext = _READ):
    doc = await _visible_or_404(ctx, resource_id)
    return {**doc, "_id": str(doc["_id"])}


@router.post("/resources", response_model=Resource, status_code=status.HTTP_201_CREATED)
async def create_resource(payload: ResourceCreate, ctx: AccessContext = _WRITE):
    try:
        return await portal_service.create_resource(payload, ctx.user_id, _is_admin(ctx))
    except PortalError as exc:
        raise _fail(exc)


def _may_manage(ctx: AccessContext, doc: dict) -> bool:
    return _is_admin(ctx) or doc["created_by"] == ctx.user_id


@router.put("/resources/{resource_id}", response_model=Resource)
async def update_resource(resource_id: str, payload: ResourceUpdate, ctx: AccessContext = _WRITE):
    doc = await _visible_or_404(ctx, resource_id)
    if not _may_manage(ctx, doc):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    if payload.visibility is not None and not _is_admin(ctx):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Solo un administrador cambia la visibilidad")
    try:
        return await portal_service.update_resource(doc, payload, ctx.user_id, _is_admin(ctx))
    except PortalError as exc:
        raise _fail(exc)


@router.delete("/resources/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resource(resource_id: str, ctx: AccessContext = _WRITE):
    doc = await _visible_or_404(ctx, resource_id)
    if not _may_manage(ctx, doc):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    await portal_service.delete_resource(doc, ctx.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
