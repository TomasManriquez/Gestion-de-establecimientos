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

from app.access.access_entity import ALL_RESOURCES, SUBJECT_UNIT, SUBJECT_USER, GrantCreate
from app.audit.audit_entity import AuditAction, AuditTarget
from app.audit.audit_service import audit_service
from app.database.database_service import db_service
from app.units.units_service import units_service
from app.users.users_service import users_service


class GrantError(Exception):
    """Error de negocio al conceder; `code` lo traduce el controller."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _plain(doc: dict) -> dict:
    return {**doc, "_id": str(doc["_id"])}


class AccessService:
    @staticmethod
    async def _subjects(user_id: str, unit_id: Optional[str]) -> list:
        """Concesiones que cubren a la persona: la suya, la de su unidad y las de unidades ancestras con subunidades."""
        unit_id = str(unit_id) if unit_id else None
        clauses = [{"subject_type": SUBJECT_USER, "subject_id": user_id}]
        unit = await units_service.find_by_id(unit_id) if unit_id else None
        if unit:
            clauses.append({"subject_type": SUBJECT_UNIT, "subject_id": unit_id})
            if unit["ancestors"]:
                clauses.append({"subject_type": SUBJECT_UNIT, "subject_id": {"$in": unit["ancestors"]},
                                "include_subunits": True})
        return clauses

    async def can(self, user_id: str, resource_type: str, resource_id: str, *, is_iam_admin: bool = False,
                  unit_id: Optional[str] = None) -> bool:
        if is_iam_admin:
            return True
        doc = await db_service.db.resource_grants.find_one({
            "resource_type": resource_type, "resource_id": {"$in": [resource_id, ALL_RESOURCES]},
            "$or": await self._subjects(user_id, unit_id),
        })
        return doc is not None

    async def visible_ids(self, user_id: str, resource_type: str, *, is_iam_admin: bool = False,
                          unit_id: Optional[str] = None) -> Optional[Set[str]]:
        """Ids con concesión, o None si la persona ve todos (admin o concesión "*"). Una sola consulta de concesiones."""
        if is_iam_admin:
            return None
        ids = {d["resource_id"] async for d in db_service.db.resource_grants.find(
            {"resource_type": resource_type, "$or": await self._subjects(user_id, unit_id)})}
        return None if ALL_RESOURCES in ids else ids

    async def list_grants(self, resource_type: Optional[str] = None, resource_id: Optional[str] = None,
                          user_id: Optional[str] = None) -> list:
        filt = {k: v for k, v in (("resource_type", resource_type), ("resource_id", resource_id),
                                  ("subject_id", user_id)) if v is not None}
        return [_plain(d) async for d in db_service.db.resource_grants.find(filt).sort("_id", 1)]

    async def create(self, data: GrantCreate, actor_id: str) -> dict:
        if data.unit_id is not None:
            unit = await units_service.find_by_id(data.unit_id)
            if unit is None:
                raise GrantError("unit_not_found")
            if unit.get("status") != "active":
                raise GrantError("unit_not_active")
            subject_type, subject_id = SUBJECT_UNIT, data.unit_id
        else:
            person = await users_service.find_by_id(data.user_id)          # nunca se concede a una cuenta que no existe
            if person is None:
                raise GrantError("user_not_found")
            if person.get("status") != "active":
                raise GrantError("user_not_active")
            subject_type, subject_id = SUBJECT_USER, data.user_id
        doc = {"resource_type": data.resource_type, "resource_id": data.resource_id, "subject_type": subject_type,
               "subject_id": subject_id, "include_subunits": data.include_subunits, "granted_by": actor_id,
               "granted_at": datetime.now(timezone.utc).replace(tzinfo=None)}
        try:
            result = await db_service.db.resource_grants.insert_one(doc)
        except DuplicateKeyError:
            raise GrantError("already_granted")
        doc["_id"] = result.inserted_id
        await audit_service.record(actor_id, AuditAction.RESOURCE_GRANT_CREATE, AuditTarget.RESOURCE_GRANT, str(doc["_id"]),
                                   {"resource_type": data.resource_type, "resource_id": data.resource_id,
                                    "subject_type": subject_type, "subject_id": subject_id,
                                    "include_subunits": data.include_subunits})
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
