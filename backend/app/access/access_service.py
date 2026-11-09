"""
access_service.py — concesiones por recurso (ADR-021).

Una concesión da `ver` a una persona sobre un recurso (o sobre todos los de un tipo con "*").
`can` y `visible_ids` solo responden por concesiones: si el recurso es público (`org`) o la persona
es `iam/admin`, quien llama lo sabe y lo pasa. Así `access` no depende de `portal` ni de `auth`, y el
service nunca recibe al usuario (L3).
"""
from datetime import datetime, timezone
from typing import Optional, Set

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.access.access_entity import ALL_RESOURCES, SUBJECT_USER, GrantCreate
from app.audit.audit_entity import AuditAction, AuditTarget
from app.audit.audit_service import audit_service
from app.database.database_service import db_service
from app.users.users_service import users_service


class GrantError(Exception):
    """Error de negocio al conceder; `code` lo traduce el controller."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _plain(doc: dict) -> dict:
    return {**doc, "_id": str(doc["_id"])}


class AccessService:
    async def can(self, user_id: str, resource_type: str, resource_id: str, *, is_iam_admin: bool = False) -> bool:
        if is_iam_admin:
            return True
        doc = await db_service.db.resource_grants.find_one({
            "resource_type": resource_type, "subject_type": SUBJECT_USER, "subject_id": user_id,
            "resource_id": {"$in": [resource_id, ALL_RESOURCES]},
        })
        return doc is not None

    async def visible_ids(self, user_id: str, resource_type: str, *, is_iam_admin: bool = False) -> Optional[Set[str]]:
        """Ids con concesión, o None si la persona ve todos (admin o concesión "*"). Una sola consulta."""
        if is_iam_admin:
            return None
        ids = {d["resource_id"] async for d in db_service.db.resource_grants.find(
            {"resource_type": resource_type, "subject_type": SUBJECT_USER, "subject_id": user_id})}
        return None if ALL_RESOURCES in ids else ids

    async def list_grants(self, resource_type: Optional[str] = None, resource_id: Optional[str] = None,
                          user_id: Optional[str] = None) -> list:
        filt = {k: v for k, v in (("resource_type", resource_type), ("resource_id", resource_id),
                                  ("subject_id", user_id)) if v is not None}
        return [_plain(d) async for d in db_service.db.resource_grants.find(filt).sort("_id", 1)]

    async def create(self, data: GrantCreate, actor_id: str) -> dict:
        person = await users_service.find_by_id(data.user_id)          # nunca se concede a una cuenta que no existe
        if person is None:
            raise GrantError("user_not_found")
        if person.get("status") != "active":
            raise GrantError("user_not_active")
        doc = {"resource_type": data.resource_type, "resource_id": data.resource_id, "subject_type": SUBJECT_USER,
               "subject_id": data.user_id, "granted_by": actor_id,
               "granted_at": datetime.now(timezone.utc).replace(tzinfo=None)}
        try:
            result = await db_service.db.resource_grants.insert_one(doc)
        except DuplicateKeyError:
            raise GrantError("already_granted")
        doc["_id"] = result.inserted_id
        await audit_service.record(actor_id, AuditAction.RESOURCE_GRANT_CREATE, AuditTarget.RESOURCE_GRANT, str(doc["_id"]),
                                   {"resource_type": data.resource_type, "resource_id": data.resource_id,
                                    "subject_id": data.user_id})
        return _plain(doc)

    async def revoke(self, grant_id: str, actor_id: str) -> bool:
        if not (isinstance(grant_id, str) and len(grant_id) == 24 and ObjectId.is_valid(grant_id)):
            return False
        oid = ObjectId(grant_id)
        doc = await db_service.db.resource_grants.find_one({"_id": oid})
        if doc is None:
            return False
        await db_service.db.resource_grants.delete_one({"_id": oid})
        await audit_service.record(actor_id, AuditAction.RESOURCE_GRANT_REVOKE, AuditTarget.RESOURCE_GRANT, grant_id,
                                   {"resource_type": doc["resource_type"], "resource_id": doc["resource_id"],
                                    "subject_id": doc["subject_id"]})
        return True

    async def purge(self, resource_type: str, resource_id: str, actor_id: str) -> int:
        """Borra las concesiones de un recurso que dejó de existir; una sola entrada de auditoría."""
        n = (await db_service.db.resource_grants.delete_many(
            {"resource_type": resource_type, "resource_id": resource_id})).deleted_count
        if n:
            await audit_service.record(actor_id, AuditAction.RESOURCE_GRANT_REVOKE, AuditTarget.RESOURCE_GRANT, resource_id,
                                       {"resource_type": resource_type, "resource_id": resource_id, "revoked": n})
        return n


access_service = AccessService()
