import logging
from typing import Dict, List, Optional

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.database.database_service import db_service
from app.units.units_entity import (CANNOT_HAVE_CHILDREN, PARENT_LEVEL, UNITS_SEED, HeadCandidate,
                                    UnitConflict, UnitCreate, UnitNotFound, UnitUpdate)

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
    async def create(self, data: UnitCreate) -> dict:
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
        return _public(doc)

    async def update(self, unit_id: str, data: UnitUpdate) -> dict:
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
        return await self.find_by_id(unit_id)

    async def move(self, unit_id: str, new_parent_id: str) -> dict:
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
        return await self.find_by_id(unit_id)

    async def deactivate(self, unit_id: str, active_users: int) -> dict:
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
        return await self.find_by_id(unit_id)

    async def activate(self, unit_id: str) -> dict:
        oid = _oid(unit_id)
        unit = await db_service.db.units.find_one({"_id": oid}) if oid else None
        if unit is None:
            raise UnitNotFound(f"Unit {unit_id} not found")
        if unit.get("parent_id"):
            parent = await db_service.db.units.find_one({"_id": unit["parent_id"]})
            if parent is None or parent["status"] != "active":
                raise UnitConflict("No se puede reactivar una unidad cuyo padre está inactivo", "inactive_parent")
        await db_service.db.units.update_one({"_id": oid}, {"$set": {"status": "active"}})
        return await self.find_by_id(unit_id)

    async def set_head(self, unit_id: str, candidate: Optional[HeadCandidate]) -> dict:
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
        return await self.find_by_id(unit_id)

    async def clear_head_for_user(self, user_id: str) -> int:
        """Lo llama `users` al desactivar a alguien (Q8): quita su jefatura si la tenía."""
        oid = _oid(user_id)
        if oid is None:
            return 0
        result = await db_service.db.units.update_many({"head_user_id": oid}, {"$set": {"head_user_id": None}})
        return result.modified_count


units_service = UnitsService()
