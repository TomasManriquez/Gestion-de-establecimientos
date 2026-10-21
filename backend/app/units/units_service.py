import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.audit.audit_entity import AuditAction, AuditTarget
from app.audit.audit_service import audit_service, diff
from app.database.database_service import db_service
from app.units.units_entity import (CANNOT_HAVE_CHILDREN, PARENT_LEVEL, UNITS_SEED, HeadCandidate,
                                    SubrogationCreate, UnitConflict, UnitCreate, UnitNotFound, UnitUpdate)

logger = logging.getLogger("units")


def _oid(value) -> Optional[ObjectId]:
    """ObjectId o None si el valor no es un id válido (un id mal formado es un 404, no un 500: D12)."""
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, str) and len(value) == 24 and ObjectId.is_valid(value):
        return ObjectId(value)
    return None


def _public(doc: dict) -> dict:
    out = dict(doc)
    out["_id"] = str(doc["_id"])
    out["parent_id"] = str(doc["parent_id"]) if doc.get("parent_id") else None
    out["ancestors"] = [str(a) for a in doc.get("ancestors", [])]
    out["head_user_id"] = str(doc["head_user_id"]) if doc.get("head_user_id") else None
    return out


class UnitsService:
    # ── seed ──────────────────────────────────────────────────────────────────
    async def ensure_bootstrap_units(self) -> None:
        """Crea la estructura de R2 solo si la colección está vacía. Los datos son una
        constante del módulo (UNITS_SEED), no un .json."""
        if await db_service.db.units.count_documents({}) != 0:
            return
        ids = {code: ObjectId() for code, *_ in UNITS_SEED}
        parent_of = {code: parent for code, _n, _l, parent, _o in UNITS_SEED}

        def ancestors(code: str) -> List[ObjectId]:
            chain, cur = [], parent_of[code]
            while cur is not None:
                chain.append(ids[cur])
                cur = parent_of[cur]
            return list(reversed(chain))

        docs = [{
            "_id": ids[code], "code": code, "name": name, "level": level,
            "parent_id": ids[parent] if parent else None,
            "ancestors": ancestors(code), "head_user_id": None, "order": order, "status": "active",
        } for code, name, level, parent, order in UNITS_SEED]
        try:
            await db_service.db.units.insert_many(docs)
            logger.info("Organigrama sembrado: %d unidades", len(docs))
        except DuplicateKeyError:
            # Otro worker de Gunicorn sembró primero: el índice único de `code` lo impide.
            logger.info("Organigrama ya sembrado por otro worker")

    # ── lecturas ──────────────────────────────────────────────────────────────
    async def find_all(self, status: Optional[str] = None, level: Optional[int] = None) -> List[dict]:
        query: Dict = {}
        if status:
            query["status"] = status
        if level:
            query["level"] = level
        cursor = db_service.db.units.find(query).sort([("level", 1), ("order", 1), ("name", 1)])
        return [_public(d) async for d in cursor]

    async def find_by_id(self, unit_id: str) -> Optional[dict]:
        oid = _oid(unit_id)
        doc = await db_service.db.units.find_one({"_id": oid}) if oid else None
        return _public(doc) if doc else None

    async def find_by_code(self, code: str) -> Optional[dict]:
        doc = await db_service.db.units.find_one({"code": code})
        return _public(doc) if doc else None

    async def tree(self, status: Optional[str] = None) -> List[dict]:
        """Árbol anidado ordenado por `order`. Las unidades cuyo padre no entra en el
        filtro de estado se ignoran junto con su rama."""
        flat = await self.find_all(status=status)
        nodes = {u["_id"]: {**u, "children": []} for u in flat}
        roots = []
        for u in flat:
            node = nodes[u["_id"]]
            parent = nodes.get(u["parent_id"]) if u["parent_id"] else None
            if parent is not None:
                parent["children"].append(node)
            elif u["parent_id"] is None:
                roots.append(node)
        key = lambda n: (n["order"], n["name"])
        for n in nodes.values():
            n["children"].sort(key=key)
        return sorted(roots, key=key)

    async def get_active_ids(self, ids) -> set:
        """Ids (str) que existen y están activos. Una sola consulta para todo un lote."""
        oids = [o for o in (_oid(i) for i in ids) if o is not None]
        if not oids:
            return set()
        cursor = db_service.db.units.find({"_id": {"$in": oids}, "status": "active"}, {"_id": 1})
        return {str(d["_id"]) async for d in cursor}

    async def subtree_ids(self, unit_id: str) -> List[str]:
        """La unidad y todos sus descendientes, con una consulta indexada sobre `ancestors`."""
        oid = _oid(unit_id)
        if oid is None:
            return []
        cursor = db_service.db.units.find({"$or": [{"_id": oid}, {"ancestors": oid}]}, {"_id": 1})
        return [str(d["_id"]) async for d in cursor]

    async def ids_by_level(self, level: int) -> List[str]:
        cursor = db_service.db.units.find({"level": level}, {"_id": 1})
        return [str(d["_id"]) async for d in cursor]

    # ── escritura ─────────────────────────────────────────────────────────────
    async def create(self, data: UnitCreate, actor_id: Optional[str] = None) -> dict:
        parent = None
        if PARENT_LEVEL[data.level] is None:
            if data.parent_id is not None:
                raise UnitConflict("La unidad de nivel 1 no tiene padre", "invalid_parent")
            if await db_service.db.units.count_documents({"level": 1}) > 0:
                raise UnitConflict("Ya existe la unidad de nivel 1", "single_root")
        else:
            poid = _oid(data.parent_id)
            if poid is None:
                raise UnitConflict(f"Una unidad de nivel {data.level} necesita un padre válido", "invalid_parent")
            parent = await db_service.db.units.find_one({"_id": poid})
            if parent is None:
                raise UnitNotFound("El padre indicado no existe")
            if parent["status"] != "active":
                raise UnitConflict("El padre está inactivo", "inactive_parent")
            if parent["level"] in CANNOT_HAVE_CHILDREN:
                raise UnitConflict(f"Una unidad de nivel {parent['level']} no puede tener hijas", "level2_no_children")
            if parent["level"] != PARENT_LEVEL[data.level]:
                raise UnitConflict(
                    f"El padre de una unidad de nivel {data.level} debe ser de nivel {PARENT_LEVEL[data.level]} "
                    f"(recibido: nivel {parent['level']})", "invalid_parent_level")
        doc = {
            "code": data.code, "name": data.name, "level": data.level,
            "parent_id": parent["_id"] if parent else None,
            "ancestors": ([*parent.get("ancestors", []), parent["_id"]] if parent else []),
            "head_user_id": None, "order": data.order, "status": "active",
        }
        try:
            result = await db_service.db.units.insert_one(doc)
        except DuplicateKeyError:
            raise UnitConflict("Ya existe una unidad con ese code o con ese nombre bajo el mismo padre", "duplicate")
        doc["_id"] = result.inserted_id
        await audit_service.record(actor_id, AuditAction.UNIT_CREATE, AuditTarget.UNIT, str(result.inserted_id), {
            "code": [None, doc["code"]], "name": [None, doc["name"]], "level": [None, doc["level"]],
            "parent_id": [None, str(doc["parent_id"]) if doc["parent_id"] else None]})
        return _public(doc)

    async def update(self, unit_id: str, data: UnitUpdate, actor_id: Optional[str] = None) -> dict:
        oid = _oid(unit_id)
        current = await db_service.db.units.find_one({"_id": oid}) if oid else None
        if current is None:
            raise UnitNotFound(f"Unit {unit_id} not found")
        changes = {k: v for k, v in data.model_dump().items() if v is not None}
        if changes:
            try:
                await db_service.db.units.update_one({"_id": oid}, {"$set": changes})
            except DuplicateKeyError:
                raise UnitConflict("Ya existe una unidad con ese nombre bajo el mismo padre", "duplicate")
        updated = await self.find_by_id(unit_id)
        changed = diff(current, updated, list(changes))
        if changed:
            await audit_service.record(actor_id, AuditAction.UNIT_UPDATE, AuditTarget.UNIT, unit_id, changed)
        return updated

    async def move(self, unit_id: str, new_parent_id: str, actor_id: Optional[str] = None) -> dict:
        """Mueve una unidad y reescribe los `ancestors` de todo su subárbol."""
        oid = _oid(unit_id)
        unit = await db_service.db.units.find_one({"_id": oid}) if oid else None
        if unit is None:
            raise UnitNotFound(f"Unit {unit_id} not found")
        poid = _oid(new_parent_id)
        parent = await db_service.db.units.find_one({"_id": poid}) if poid else None
        if parent is None:
            raise UnitNotFound("El nuevo padre no existe")
        if PARENT_LEVEL[unit["level"]] is None:
            raise UnitConflict("La unidad de nivel 1 no se puede mover", "root_immovable")
        if parent["_id"] == oid or oid in parent.get("ancestors", []):
            raise UnitConflict("No se puede mover una unidad dentro de su propio subárbol", "cycle")
        if parent["status"] != "active":
            raise UnitConflict("El nuevo padre está inactivo", "inactive_parent")
        if parent["level"] in CANNOT_HAVE_CHILDREN or parent["level"] != PARENT_LEVEL[unit["level"]]:
            raise UnitConflict(
                f"El padre de una unidad de nivel {unit['level']} debe ser de nivel {PARENT_LEVEL[unit['level']]}",
                "invalid_parent_level")
        new_anc = [*parent.get("ancestors", []), parent["_id"]]
        try:
            await db_service.db.units.update_one({"_id": oid}, {"$set": {"parent_id": parent["_id"], "ancestors": new_anc}})
        except DuplicateKeyError:
            raise UnitConflict("Ya existe una unidad con ese nombre bajo el nuevo padre", "duplicate")
        # Subárbol: ancestors = new_anc + [esta unidad] + (lo que había debajo de ella)
        async for child in db_service.db.units.find({"ancestors": oid}):
            idx = child["ancestors"].index(oid)
            tail = child["ancestors"][idx + 1:]
            await db_service.db.units.update_one({"_id": child["_id"]}, {"$set": {"ancestors": [*new_anc, oid, *tail]}})
        await audit_service.record(actor_id, AuditAction.UNIT_MOVE, AuditTarget.UNIT, unit_id, {
            "parent_id": [str(unit["parent_id"]) if unit.get("parent_id") else None, str(parent["_id"])]})
        return await self.find_by_id(unit_id)

    async def deactivate(self, unit_id: str, active_users: int, actor_id: Optional[str] = None) -> dict:
        """`active_users` lo calcula el controller con `users_service` (ADR-013)."""
        oid = _oid(unit_id)
        unit = await db_service.db.units.find_one({"_id": oid}) if oid else None
        if unit is None:
            raise UnitNotFound(f"Unit {unit_id} not found")
        if active_users > 0:
            raise UnitConflict(f"La unidad tiene {active_users} usuario(s) activo(s)", "has_active_users")
        if await db_service.db.units.count_documents({"parent_id": oid, "status": "active"}) > 0:
            raise UnitConflict("La unidad tiene unidades hijas activas", "has_active_children")
        await db_service.db.units.update_one({"_id": oid}, {"$set": {"status": "inactive"}})
        await audit_service.record(actor_id, AuditAction.UNIT_DEACTIVATE, AuditTarget.UNIT, unit_id,
                                   {"status": [unit.get("status"), "inactive"]})
        return await self.find_by_id(unit_id)

    async def activate(self, unit_id: str, actor_id: Optional[str] = None) -> dict:
        oid = _oid(unit_id)
        unit = await db_service.db.units.find_one({"_id": oid}) if oid else None
        if unit is None:
            raise UnitNotFound(f"Unit {unit_id} not found")
        if unit.get("parent_id"):
            parent = await db_service.db.units.find_one({"_id": unit["parent_id"]})
            if parent is None or parent["status"] != "active":
                raise UnitConflict("No se puede reactivar una unidad cuyo padre está inactivo", "inactive_parent")
        await db_service.db.units.update_one({"_id": oid}, {"$set": {"status": "active"}})
        await audit_service.record(actor_id, AuditAction.UNIT_ACTIVATE, AuditTarget.UNIT, unit_id,
                                   {"status": [unit.get("status"), "active"]})
        return await self.find_by_id(unit_id)

    async def set_head(self, unit_id: str, candidate: Optional[HeadCandidate], actor_id: Optional[str] = None) -> dict:
        """Fija o quita la jefatura. El candidato lo resuelve el controller (ADR-013).
        Regla (Q7): funcionario SLEP activo y miembro de la propia unidad."""
        oid = _oid(unit_id)
        unit = await db_service.db.units.find_one({"_id": oid}) if oid else None
        if unit is None:
            raise UnitNotFound(f"Unit {unit_id} not found")
        if candidate is None:
            await db_service.db.units.update_one({"_id": oid}, {"$set": {"head_user_id": None}})
        else:
            if not candidate.active:
                raise UnitConflict("La jefatura debe ser un usuario activo", "head_inactive")
            if not candidate.is_slep_staff:
                raise UnitConflict("La jefatura debe ser funcionario SLEP", "head_not_slep_staff")
            if candidate.unit_id != str(oid):
                raise UnitConflict("La jefatura debe pertenecer a la propia unidad", "head_not_member")
            await db_service.db.units.update_one({"_id": oid}, {"$set": {"head_user_id": ObjectId(candidate.id)}})
        await audit_service.record(actor_id, AuditAction.UNIT_HEAD, AuditTarget.UNIT, unit_id, {
            "head_user_id": [str(unit["head_user_id"]) if unit.get("head_user_id") else None, candidate.id if candidate else None]})
        return await self.find_by_id(unit_id)

    # ══ Subrogancias (E1b, ADR-010): colección propia, «vigente» se calcula por fecha ═════════
    @staticmethod
    def _subrogation_public(doc: dict, now: Optional[datetime] = None) -> dict:
        now = now or datetime.now(timezone.utc).replace(tzinfo=None)
        out = dict(doc)
        for key in ("_id", "unit_id", "subrogate_user_id", "created_by"):
            out[key] = str(doc[key]) if doc.get(key) else None
        out["current"] = (doc.get("cancelled_at") is None and doc["starts_at"] <= now
                          and (doc.get("ends_at") is None or now < doc["ends_at"]))
        return out

    async def create_subrogation(self, unit_id: str, data: SubrogationCreate, candidate: Optional[HeadCandidate],
                                 actor_id: Optional[str] = None) -> dict:
        """`candidate` lo resuelve el controller con `users_service` (ADR-013). Reglas: la unidad existe y
        está activa; el subrogante es un funcionario SLEP activo, de la unidad o de su subárbol, y no es la
        jefatura titular; no se superponen dos vigentes en la misma unidad."""
        oid = _oid(unit_id)
        unit = await db_service.db.units.find_one({"_id": oid}) if oid else None
        if unit is None:
            raise UnitNotFound(f"Unit {unit_id} not found")
        if unit.get("status") != "active":
            raise UnitConflict("La unidad está inactiva", "inactive_unit")
        if candidate is None:
            raise UnitNotFound(f"User {data.subrogate_user_id} not found")
        if not candidate.active:
            raise UnitConflict("El subrogante debe ser un usuario activo", "subrogate_inactive")
        if not candidate.is_slep_staff:
            raise UnitConflict("El subrogante debe ser funcionario SLEP", "head_not_slep_staff")
        if candidate.unit_id not in await self.subtree_ids(unit_id):
            raise UnitConflict("El subrogante debe pertenecer a la unidad o a su subárbol", "subrogate_not_member")
        if unit.get("head_user_id") and str(unit["head_user_id"]) == candidate.id:
            raise UnitConflict("El subrogante no puede ser la jefatura titular", "subrogate_is_head")
        async for other in db_service.db.subrogations.find({"unit_id": oid, "cancelled_at": None}):
            starts_before_other_ends = other.get("ends_at") is None or data.starts_at < other["ends_at"]
            ends_after_other_starts = data.ends_at is None or data.ends_at > other["starts_at"]
            if starts_before_other_ends and ends_after_other_starts:
                raise UnitConflict("Ya hay una subrogancia que se superpone en esas fechas", "subrogation_overlap")
        doc = {
            "unit_id": oid, "subrogate_user_id": ObjectId(candidate.id), "starts_at": data.starts_at,
            "ends_at": data.ends_at, "reason": data.reason.value, "document_ref": data.document_ref,
            "created_by": _oid(actor_id), "created_at": datetime.now(timezone.utc).replace(tzinfo=None), "cancelled_at": None,
        }
        result = await db_service.db.subrogations.insert_one(doc)
        doc["_id"] = result.inserted_id
        await audit_service.record(actor_id, AuditAction.SUBROGATION_CREATE, AuditTarget.SUBROGATION, str(result.inserted_id), {
            "unit_id": [None, unit_id], "subrogate_user_id": [None, candidate.id], "reason": [None, doc["reason"]],
            "starts_at": [None, doc["starts_at"]], "ends_at": [None, doc["ends_at"]]})
        return self._subrogation_public(doc)

    async def list_subrogations(self, unit_id: str, only_current: bool = False) -> List[dict]:
        oid = _oid(unit_id)
        if oid is None or await db_service.db.units.find_one({"_id": oid}) is None:
            raise UnitNotFound(f"Unit {unit_id} not found")
        cursor = db_service.db.subrogations.find({"unit_id": oid}).sort([("starts_at", -1)])
        items = [self._subrogation_public(d) async for d in cursor]
        return [i for i in items if i["current"]] if only_current else items

    async def cancel_subrogation(self, subrogation_id: str, actor_id: Optional[str] = None) -> dict:
        oid = _oid(subrogation_id)
        doc = await db_service.db.subrogations.find_one({"_id": oid}) if oid else None
        if doc is None:
            raise UnitNotFound(f"Subrogation {subrogation_id} not found")
        if doc.get("cancelled_at") is None:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            await db_service.db.subrogations.update_one({"_id": oid}, {"$set": {"cancelled_at": now}})
            doc["cancelled_at"] = now
            await audit_service.record(actor_id, AuditAction.SUBROGATION_CANCEL, AuditTarget.SUBROGATION, subrogation_id,
                                       {"cancelled_at": [None, now]})
        return self._subrogation_public(doc)

    async def acting_user_ids(self) -> List[str]:
        """Usuarios que subrogan HOY (filtro `acting` del listado de usuarios)."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        cursor = db_service.db.subrogations.find({"cancelled_at": None, "starts_at": {"$lte": now}})
        return sorted({str(d["subrogate_user_id"]) async for d in cursor if d.get("ends_at") is None or now < d["ends_at"]})

    async def clear_head_for_user(self, user_id: str) -> int:
        """Lo llama `users` al desactivar a alguien (Q8): quita su jefatura si la tenía."""
        oid = _oid(user_id)
        if oid is None:
            return 0
        result = await db_service.db.units.update_many({"head_user_id": oid}, {"$set": {"head_user_id": None}})
        return result.modified_count


units_service = UnitsService()
