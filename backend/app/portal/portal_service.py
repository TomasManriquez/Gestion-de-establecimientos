"""
portal_service.py — temas (dos niveles) y recursos del portal (ADR-021).

El tema ordena, no da permisos. Quién ve un recurso lo decide `visibility` (`org` o `restricted`) y, para
`restricted`, las concesiones de `access`. El service no recibe al usuario (L3): recibe ids y booleanos.
"""
from datetime import datetime, timezone
from typing import Optional, Set
from urllib.parse import urlparse

from bson import ObjectId

from app.access.access_entity import GrantCreate
from app.access.access_service import GrantError, access_service
from app.audit.audit_entity import AuditAction, AuditTarget
from app.audit.audit_service import audit_service, diff
from app.database.database_service import db_service
from app.portal.portal_entity import (CATASTRO_RESTRICTED, ResourceCreate, ResourceUpdate, TopicCreate)
from app.units.units_service import units_service

RESOURCE_TYPE = "portal_resource"
_TRACKED = ("title", "url", "description", "topic_id", "unit_id", "catastro_level", "visibility")
# shortcut: tabla fija de plataformas conocidas; cualquier otra se muestra por su host. Ampliar si aparece una nueva.
_PLATFORMS = (("docs.google.com/spreadsheets", "Google Sheets"), ("docs.google.com", "Google Docs"),
              ("drive.google.com", "Google Drive"), ("lookerstudio.google.com", "Looker Studio"),
              ("powerbi.com", "Power BI"), ("sharepoint.com", "SharePoint"))


class PortalError(Exception):
    """Error de negocio; `code` lo traduce el controller."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def detect_platform(url: str) -> str:
    parsed = urlparse(url)
    host_path = f"{(parsed.hostname or '').lower()}{parsed.path}"
    return next((name for frag, name in _PLATFORMS if frag in host_path), parsed.hostname or "Enlace")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _oid(value: str) -> Optional[ObjectId]:
    return ObjectId(value) if isinstance(value, str) and len(value) == 24 and ObjectId.is_valid(value) else None


def _plain(doc: dict) -> dict:
    return {**doc, "_id": str(doc["_id"])}


class PortalService:
    # ---- temas ------------------------------------------------------------------------------------------
    async def list_topics(self) -> list:
        return [_plain(d) async for d in db_service.db.portal_topics.find({}).sort("name", 1)]

    async def _topic(self, topic_id: str) -> Optional[dict]:
        oid = _oid(topic_id)
        return None if oid is None else await db_service.db.portal_topics.find_one({"_id": oid})

    async def create_topic(self, data: TopicCreate, actor_id: str) -> dict:
        if data.parent_id is not None:
            parent = await self._topic(data.parent_id)
            if parent is None:
                raise PortalError("parent_not_found")
            if parent.get("parent_id"):
                raise PortalError("topic_too_deep")           # máximo dos niveles
        doc = {"name": data.name, "parent_id": data.parent_id}
        doc["_id"] = (await db_service.db.portal_topics.insert_one(doc)).inserted_id
        await audit_service.record(actor_id, AuditAction.PORTAL_TOPIC_CREATE, AuditTarget.PORTAL_TOPIC, str(doc["_id"]),
                                   {"name": data.name, "parent_id": data.parent_id})
        return _plain(doc)

    async def rename_topic(self, topic_id: str, name: str, actor_id: str) -> Optional[dict]:
        before = await self._topic(topic_id)
        if before is None:
            return None
        await db_service.db.portal_topics.update_one({"_id": before["_id"]}, {"$set": {"name": name}})
        await audit_service.record(actor_id, AuditAction.PORTAL_TOPIC_UPDATE, AuditTarget.PORTAL_TOPIC, topic_id,
                                   diff(before, {**before, "name": name}, ("name",)))
        return _plain({**before, "name": name})

    async def delete_topic(self, topic_id: str, actor_id: str) -> bool:
        before = await self._topic(topic_id)
        if before is None:
            return False
        if await db_service.db.portal_topics.find_one({"parent_id": topic_id}) or \
                await db_service.db.portal_resources.find_one({"topic_id": topic_id}):
            raise PortalError("topic_in_use")                 # nunca deja recursos huérfanos
        await db_service.db.portal_topics.delete_one({"_id": before["_id"]})
        await audit_service.record(actor_id, AuditAction.PORTAL_TOPIC_DELETE, AuditTarget.PORTAL_TOPIC, topic_id,
                                   {"name": before["name"]})
        return True

    # ---- recursos ---------------------------------------------------------------------------------------
    async def _check_refs(self, topic_id: Optional[str], unit_id: Optional[str]) -> None:
        if topic_id is not None and await self._topic(topic_id) is None:
            raise PortalError("topic_not_found")
        if unit_id is not None and await units_service.find_by_id(unit_id) is None:
            raise PortalError("unit_not_found")

    async def find_resource(self, resource_id: str) -> Optional[dict]:
        oid = _oid(resource_id)
        return None if oid is None else await db_service.db.portal_resources.find_one({"_id": oid})

    async def list_resources(self, visible: Optional[Set[str]], topic_id: Optional[str] = None) -> list:
        """`visible` = ids con concesión (o None si la persona ve todo). Los `org` salen siempre."""
        filt: dict = {} if topic_id is None else {"topic_id": topic_id}
        if visible is not None:
            filt["$or"] = [{"visibility": "org"}, {"_id": {"$in": [o for o in map(_oid, visible) if o]}}]
        return [_plain(d) async for d in db_service.db.portal_resources.find(filt).sort("title", 1)]

    async def create_resource(self, data: ResourceCreate, actor_id: str, is_admin: bool) -> dict:
        await self._check_refs(data.topic_id, data.unit_id)
        now = _now()
        visibility = "restricted" if data.catastro_level >= CATASTRO_RESTRICTED else "org"
        doc = {**data.model_dump(), "platform": detect_platform(data.url), "visibility": visibility,
               "created_by": actor_id, "created_at": now, "updated_by": actor_id, "updated_at": now}
        doc["_id"] = (await db_service.db.portal_resources.insert_one(doc)).inserted_id
        if visibility == "restricted" and not is_admin:
            await self._grant_registrar(str(doc["_id"]), actor_id)
        await audit_service.record(actor_id, AuditAction.PORTAL_RESOURCE_CREATE, AuditTarget.PORTAL_RESOURCE,
                                   str(doc["_id"]), {f: doc[f] for f in _TRACKED})
        return _plain(doc)

    async def _grant_registrar(self, resource_id: str, actor_id: str) -> None:
        # El registrador ve lo que acaba de registrar (ADR-021 §5); las demás personas las agrega un admin.
        try:
            await access_service.create(GrantCreate(resource_type=RESOURCE_TYPE, resource_id=resource_id, user_id=actor_id), actor_id)
        except GrantError as exc:
            if exc.code != "already_granted":
                raise

    async def update_resource(self, before: dict, data: ResourceUpdate, actor_id: str, is_admin: bool) -> dict:
        sent = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None or k in ("description", "unit_id")}
        await self._check_refs(sent.get("topic_id"), sent.get("unit_id"))
        if "url" in sent:
            sent["platform"] = detect_platform(sent["url"])
        # Subir el nivel a 2 restringe sin esperar al admin; bajarlo no abre nada por sí solo (solo `visibility` lo hace).
        if sent.get("catastro_level", 0) >= CATASTRO_RESTRICTED and "visibility" not in sent:
            sent["visibility"] = "restricted"
        fields = {**sent, "updated_by": actor_id, "updated_at": _now()}
        await db_service.db.portal_resources.update_one({"_id": before["_id"]}, {"$set": fields})
        after = {**before, **fields}
        if after["visibility"] == "restricted" and before["visibility"] != "restricted" and not is_admin:
            await self._grant_registrar(str(before["_id"]), actor_id)     # quien lo restringe no se queda sin verlo
        await audit_service.record(actor_id, AuditAction.PORTAL_RESOURCE_UPDATE, AuditTarget.PORTAL_RESOURCE,
                                   str(before["_id"]), diff(before, after, _TRACKED))
        return _plain(after)

    async def delete_resource(self, before: dict, actor_id: str) -> None:
        rid = str(before["_id"])
        await db_service.db.portal_resources.delete_one({"_id": before["_id"]})
        await access_service.purge(RESOURCE_TYPE, rid, actor_id)      # sin recurso no quedan concesiones sueltas
        await audit_service.record(actor_id, AuditAction.PORTAL_RESOURCE_DELETE, AuditTarget.PORTAL_RESOURCE, rid,
                                   {f: before.get(f) for f in ("title", "url", "visibility")})


portal_service = PortalService()
