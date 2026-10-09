"""
audit_service.py — registro de auditoría de solo agregado (ADR-014).

Este módulo NO expone ninguna operación que edite o borre (un test lo verifica). `record` nunca
lanza: si la escritura falla, el cambio ya hecho NO se revierte (no hay transacciones entre
colecciones en este diseño), se registra en nivel CRITICAL y la respuesta HTTP lo indica con la
cabecera `X-Audit-Status: failed` (`AuditStatusMiddleware`).
"""
import contextvars
import logging
import math
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from bson import ObjectId

from app.audit.audit_entity import FORBIDDEN_KEYS, MASK, MASKED_KEYS, AuditAction, AuditTarget
from app.database.database_service import db_service

logger = logging.getLogger("audit")

AUDIT_HEADER = b"x-audit-status"

# Objeto mutable por petición: el middleware lo crea, `record` lo marca. Es mutable a propósito:
# el endpoint puede correr en otra tarea o hilo, y un ContextVar reasignado allí no volvería.
_failure: contextvars.ContextVar = contextvars.ContextVar("audit_failure", default=None)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _oid(value) -> Optional[ObjectId]:
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, str) and len(value) == 24 and ObjectId.is_valid(value):
        return ObjectId(value)
    return None


def _plain(value: Any) -> Any:
    """Valor apto para guardar y para mostrar: sin ObjectId, enums ni datetimes crudos."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (ObjectId, datetime)):
        return value.isoformat() if isinstance(value, datetime) else str(value)
    if isinstance(value, dict):
        return clean_changes(value)
    if isinstance(value, (list, tuple, set)):
        return [_plain(v) for v in value]
    return value


def clean_changes(changes: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Quita las claves prohibidas (en cualquier nivel) y enmascara los datos personales."""
    out: Dict[str, Any] = {}
    for key, value in (changes or {}).items():
        if str(key).lower() in FORBIDDEN_KEYS:
            continue
        if str(key).lower() in MASKED_KEYS:
            out[key] = [MASK, MASK]
            continue
        out[key] = _plain(value)
    return out


def diff(before: Dict[str, Any], after: Dict[str, Any], fields) -> Dict[str, List[Any]]:
    """`{campo: [antes, después]}` solo de los campos que cambiaron."""
    return {f: [before.get(f), after.get(f)] for f in fields if before.get(f) != after.get(f)}


class AuditService:
    async def record(self, actor_id: Optional[str], action: AuditAction, target_type: AuditTarget,
                     target_id: str, changes: Optional[Dict[str, Any]] = None,
                     bulk_id: Optional[str] = None) -> bool:
        """Agrega un registro. Devuelve False (sin lanzar) si no se pudo escribir."""
        doc = {
            "at": _utcnow(),
            "actor_id": _oid(actor_id),
            "action": action.value if isinstance(action, Enum) else str(action),
            "target_type": target_type.value if isinstance(target_type, Enum) else str(target_type),
            "target_id": str(target_id),
            "changes": clean_changes(changes),
            "bulk_id": bulk_id,
        }
        try:
            await db_service.db.audit_log.insert_one(doc)
            return True
        except Exception:  # noqa: BLE001 — la auditoría no puede tumbar la operación ya hecha
            logger.critical("No se pudo escribir en audit_log: action=%s target=%s/%s actor=%s",
                            doc["action"], doc["target_type"], doc["target_id"], actor_id, exc_info=True)
            holder = _failure.get()
            if holder is not None:
                holder["failed"] = True
            return False

    async def list_entries(self, actor_id: Optional[str] = None, action: Optional[str] = None,
                           target_type: Optional[str] = None, target_id: Optional[str] = None,
                           bulk_id: Optional[str] = None, since: Optional[datetime] = None,
                           until: Optional[datetime] = None, page: int = 1, page_size: int = 100) -> dict:
        filt: Dict[str, Any] = {}
        if actor_id:
            filt["actor_id"] = _oid(actor_id) or "__no_match__"
        for key, value in (("action", action), ("target_type", target_type),
                           ("target_id", target_id), ("bulk_id", bulk_id)):
            if value:
                filt[key] = value
        if since or until:
            filt["at"] = {**({"$gte": since} if since else {}), **({"$lte": until} if until else {})}
        total = await db_service.db.audit_log.count_documents(filt)
        cursor = (db_service.db.audit_log.find(filt).sort([("at", -1), ("_id", -1)])
                  .skip((page - 1) * page_size).limit(page_size))
        items = []
        async for d in cursor:
            items.append({**d, "_id": str(d["_id"]), "actor_id": str(d["actor_id"]) if d.get("actor_id") else None})
        return {"items": items, "total": total, "page": page, "page_size": page_size,
                "total_pages": max(1, math.ceil(total / page_size))}

    @staticmethod
    def new_bulk_id() -> str:
        return uuid.uuid4().hex


class AuditStatusMiddleware:
    """ASGI puro (no BaseHTTPMiddleware: éste ejecuta el endpoint en otra tarea). Agrega
    `X-Audit-Status: failed` a la respuesta si alguna escritura de auditoría falló durante ella."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        holder: Dict[str, bool] = {"failed": False}
        token = _failure.set(holder)

        async def send_wrapper(message):
            if message["type"] == "http.response.start" and holder["failed"]:
                message = {**message, "headers": [*message.get("headers", []), (AUDIT_HEADER, b"failed")]}
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            _failure.reset(token)


audit_service = AuditService()
