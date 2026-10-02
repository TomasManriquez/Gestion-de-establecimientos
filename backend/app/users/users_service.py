import logging
import math
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional

from bson import ObjectId
from pydantic import ValidationError
from pymongo.errors import DuplicateKeyError

from app.config import settings
from app.database.database_service import db_service
from app.establishments.establishments_service import establishments_service
from app.platforms.platforms_service import platforms_service
from app.units.units_entity import HeadCandidate
from app.units.units_service import units_service
from app.users.users_entity import (UserAdminUpdate, UserConflict, UserCreate, UserInvalid,
                                    UserNotFound, UserSelfUpdate, check_mode, normalize_email)

logger = logging.getLogger("users")

# `last_activity_at` se escribe como máximo una vez cada tanto por usuario (supuesto A5).
ACTIVITY_THROTTLE = timedelta(minutes=5)
# Tope por lote de altas y de operaciones masivas (supuesto A2).
BULK_MAX_ITEMS = 200
# Unidad a la que se asigna el admin sembrado (Q4). Si no existe, se usa la raíz.
BOOTSTRAP_ADMIN_UNIT_CODE = "AF-TI"
INVITATION_NOT_CONFIGURED = "mail_not_configured"

# Proyección de inclusión del listado: personal_phone y auth_providers quedan fuera por
# omisión (lista blanca, igual que LISTING_PROJECTION de establecimientos).
USERS_LISTING_PROJECTION = {
    "_id": 1, "email": 1, "first_name": 1, "last_name": 1, "work_extension": 1,
    "is_slep_staff": 1, "unit_id": 1, "rbd": 1, "positions": 1, "status": 1,
    "access": 1, "invitation": 1, "last_login_at": 1, "last_activity_at": 1,
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)   # MongoDB guarda UTC sin zona


def _oid(value) -> Optional[ObjectId]:
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, str) and len(value) == 24 and ObjectId.is_valid(value):
        return ObjectId(value)
    return None


def _stringify(value):
    """ObjectId -> str, recursivo. Los services devuelven ids como string (convención del proyecto)."""
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, dict):
        return {k: _stringify(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_stringify(v) for v in value]
    return value


def _has_credential(doc: dict) -> bool:
    for p in doc.get("auth_providers", []):
        if p.get("provider") == "local" and p.get("hashed_password"):
            return True
        if p.get("provider") == "google" and p.get("subject"):
            return True
    return False


def _is_iam_admin(doc: dict) -> bool:
    return any(a.get("platform_id") == "iam" and a.get("role") == "admin" for a in doc.get("access", []))


def _validation_errors(exc: ValidationError) -> List[dict]:
    out = []
    for e in exc.errors():
        loc = ".".join(str(p) for p in e["loc"]) or "_"
        out.append({"field": loc, "code": e["type"], "message": e["msg"].removeprefix("Value error, ")})
    return out


class UsersService:
    # ══ Lecturas ═══════════════════════════════════════════════════════════════
    async def find_by_id(self, user_id: str) -> Optional[dict]:
        oid = _oid(user_id)
        doc = await db_service.db.users.find_one({"_id": oid}) if oid else None
        return _stringify(doc) if doc else None

    async def find_by_login(self, login: str) -> Optional[dict]:
        """Por correo (normalizado) o, si no tiene '@', por el username legado del admin sembrado."""
        if not isinstance(login, str) or not login.strip():
            return None
        login = login.strip()
        query = {"email": normalize_email(login)} if "@" in login else {"username": login}
        doc = await db_service.db.users.find_one(query)
        return _stringify(doc) if doc else None

    async def find_for_session(self, sub: str) -> Optional[dict]:
        """Resuelve el `sub` del JWT: `str(_id)` y, mientras dure la compatibilidad, el username legado."""
        if not isinstance(sub, str) or not sub:
            return None
        oid = _oid(sub)
        if oid is not None:
            doc = await db_service.db.users.find_one({"_id": oid})
        else:
            doc = await db_service.db.users.find_one({"username": sub})
        return _stringify(doc) if doc else None

    async def count_active_in_unit(self, unit_id: str) -> int:
        oid = _oid(unit_id)
        if oid is None:
            return 0
        return await db_service.db.users.count_documents({"unit_id": oid, "status": "active"})

    async def head_candidate(self, user_id: str) -> Optional[HeadCandidate]:
        """Lo que `units` necesita saber de un usuario para fijarlo como jefatura (ADR-013)."""
        doc = await self.find_by_id(user_id)
        if doc is None:
            return None
        return HeadCandidate(id=doc["_id"], active=doc["status"] == "active",
                             is_slep_staff=bool(doc.get("is_slep_staff")), unit_id=doc.get("unit_id"))

    async def display_names(self, user_ids) -> Dict[str, str]:
        """id -> nombre a mostrar. Solo nombre y apellido: nunca correo ni teléfono."""
        oids = [o for o in (_oid(i) for i in user_ids) if o is not None]
        if not oids:
            return {}
        cursor = db_service.db.users.find({"_id": {"$in": oids}}, {"first_name": 1, "last_name": 1})
        return {str(d["_id"]): f"{d.get('first_name', '')} {d.get('last_name', '')}".strip() async for d in cursor}

    async def list_users(self, q: Optional[str] = None, unit_id: Optional[str] = None,
                         include_descendants: bool = False, level: Optional[int] = None,
                         kind: Optional[str] = None, rbd: Optional[str] = None,
                         position: Optional[str] = None, platform: Optional[str] = None,
                         role: Optional[str] = None, status: Optional[str] = None,
                         page: int = 1, page_size: int = 100) -> dict:
        query: Dict = {}
        and_clauses: List[dict] = []
        if q:
            pattern = re.escape(q.strip())     # D5: el texto del usuario nunca es una expresión regular
            query["$or"] = [{f: {"$regex": pattern, "$options": "i"}} for f in ("first_name", "last_name", "email")]
        if unit_id:
            if include_descendants:
                ids = [ObjectId(i) for i in await units_service.subtree_ids(unit_id)]
                and_clauses.append({"unit_id": {"$in": ids}})
            else:
                and_clauses.append({"unit_id": _oid(unit_id)})
        if level:
            ids = [ObjectId(i) for i in await units_service.ids_by_level(level)]
            and_clauses.append({"unit_id": {"$in": ids}})
        if kind == "slep":
            query["is_slep_staff"] = True
        elif kind == "establishment":
            query["is_slep_staff"] = False
        if rbd:
            query["rbd"] = rbd
        if position:
            query["positions"] = position
        if platform and role:
            query["access"] = {"$elemMatch": {"platform_id": platform, "role": role}}
        elif platform:
            query["access.platform_id"] = platform
        elif role:
            query["access.role"] = role
        if status:
            query["status"] = status
        if and_clauses:
            query["$and"] = and_clauses

        total = await db_service.db.users.count_documents(query)
        cursor = (db_service.db.users.find(query, USERS_LISTING_PROJECTION)
                  .sort([("last_name", 1), ("first_name", 1)]).skip((page - 1) * page_size).limit(page_size))
        items = [_stringify(d) async for d in cursor]
        return {"items": items, "total": total, "page": page, "page_size": page_size,
                "total_pages": math.ceil(total / page_size) if total > 0 else 1}

    # ══ Alta: UNA sola ruta para alta individual, CSV, bulk y seed (R6) ═════════
    async def create_many(self, items: List[dict], actor_id: Optional[str], dry_run: bool = False,
                          status: str = "invited", local_password_hash: Optional[str] = None,
                          must_change_password: bool = False, bulk_id: Optional[str] = None) -> dict:
        """normalizar -> validar -> resolver referencias en lote -> detectar duplicados
        (dentro del lote y contra la base) -> insertar. `status` y `local_password_hash` son
        opciones internas (las usa el bootstrap): ningún body HTTP las puede fijar."""
        bulk_id = bulk_id or uuid.uuid4().hex
        results: List[dict] = [{"index": i, "status": "pending", "id": None, "errors": []} for i in range(len(items))]
        parsed: Dict[int, UserCreate] = {}

        # 1. Validación (las mismas reglas del modelo para toda ruta de entrada)
        for i, raw in enumerate(items):
            try:
                parsed[i] = UserCreate.model_validate(raw)
            except ValidationError as exc:
                results[i].update(status="invalid", errors=_validation_errors(exc))

        # 2. Referencias, una consulta por colección para todo el lote
        wanted_units = {u.unit_id for u in parsed.values() if u.unit_id}
        wanted_rbds = {u.rbd for u in parsed.values() if u.rbd}
        active_units = await units_service.get_active_ids(wanted_units) if wanted_units else set()
        known_rbds = await establishments_service.existing_rbds(wanted_rbds) if wanted_rbds else set()
        for i, u in list(parsed.items()):
            errs = []
            if u.unit_id and u.unit_id not in active_units:
                errs.append({"field": "unit_id", "code": "unit_not_found", "message": "La unidad no existe o está inactiva"})
            if u.rbd and u.rbd not in known_rbds:
                errs.append({"field": "rbd", "code": "rbd_not_found", "message": f"El establecimiento con RBD {u.rbd} no existe"})
            if errs:
                results[i].update(status="invalid", errors=errs)
                del parsed[i]

        # 3. Duplicados dentro del lote (la primera fila queda válida) y contra la base
        seen: Dict[str, int] = {}
        for i, u in list(parsed.items()):
            if u.email in seen:
                results[i].update(status="duplicate", errors=[{
                    "field": "email", "code": "duplicate_in_batch",
                    "message": f"Correo repetido: ya aparece en la fila {seen[u.email] + 1}"}])
                del parsed[i]
            else:
                seen[u.email] = i
        if parsed:
            emails = [u.email for u in parsed.values()]
            existing = {d["email"] async for d in db_service.db.users.find({"email": {"$in": emails}}, {"email": 1})}
            for i, u in list(parsed.items()):
                if u.email in existing:
                    results[i].update(status="duplicate", errors=[{
                        "field": "email", "code": "duplicate", "message": "Ya existe un usuario con ese correo"}])
                    del parsed[i]

        # 4. Inserción (el índice único es la garantía final: una carrera da DuplicateKeyError)
        now = _utcnow()
        actor = _oid(actor_id)
        for i, u in parsed.items():
            if dry_run:
                results[i]["status"] = "ok"
                continue
            doc = self._new_document(u, status, actor, now, local_password_hash, must_change_password)
            try:
                inserted = await db_service.db.users.insert_one(doc)
            except DuplicateKeyError:
                results[i].update(status="duplicate", errors=[{
                    "field": "email", "code": "duplicate", "message": "Ya existe un usuario con ese correo"}])
                continue
            results[i].update(status="created", id=str(inserted.inserted_id))

        created = sum(1 for r in results if r["status"] in ("created", "ok"))
        return {"bulk_id": bulk_id, "dry_run": dry_run, "total": len(items), "created": created,
                "failed": len(items) - created, "items": results}

    @staticmethod
    def _new_document(u: UserCreate, status: str, actor, now, password_hash, must_change) -> dict:
        providers = []
        if password_hash:
            providers.append({"provider": "local", "hashed_password": password_hash,
                              "password_changed_at": None, "must_change_password": must_change})
        return {
            "email": u.email, "first_name": u.first_name, "last_name": u.last_name,
            "personal_phone": u.personal_phone, "work_extension": u.work_extension,
            "is_slep_staff": u.is_slep_staff, "unit_id": _oid(u.unit_id), "rbd": u.rbd,
            "positions": [p.value for p in u.positions],
            "status": status, "auth_providers": providers, "access": [],
            # Hasta que `auth` emita invitaciones (F4) nadie envió nada: se dice tal cual.
            "invitation": ({"sent_at": None, "expires_at": None, "last_error": INVITATION_NOT_CONFIGURED}
                           if status == "invited" else None),
            "last_login_at": None, "last_activity_at": None,
            "created_at": now, "created_by": actor, "updated_at": now, "updated_by": actor, "disabled_at": None,
        }

    async def create(self, item: dict, actor_id: Optional[str]) -> dict:
        """Alta individual = `create_many([item])`. Devuelve el usuario creado o lanza el error de dominio."""
        result = await self.create_many([item], actor_id)
        row = result["items"][0]
        if row["status"] == "created":
            return await self.find_by_id(row["id"])
        if row["status"] == "duplicate":
            raise UserConflict(row["errors"][0]["message"], row["errors"][0]["code"], field="email")
        raise UserInvalid(row["errors"])

    # ══ Edición ════════════════════════════════════════════════════════════════
    async def update(self, user_id: str, data: UserAdminUpdate, actor_id: Optional[str]) -> dict:
        current = await self._load(user_id)
        changes = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
        positions = changes.get("positions")
        if positions is not None:
            changes["positions"] = [p.value if hasattr(p, "value") else p for p in positions]

        merged = {k: current.get(k) for k in ("is_slep_staff", "unit_id", "rbd", "positions")}
        merged["unit_id"] = str(merged["unit_id"]) if merged["unit_id"] else None
        merged["positions"] = list(merged.get("positions") or [])
        # Cambiar de modo limpia los campos del otro modo (como el Switch del formulario)
        if "is_slep_staff" in changes and changes["is_slep_staff"] != merged["is_slep_staff"]:
            if changes["is_slep_staff"]:
                merged.update(rbd=None, positions=[])
            else:
                merged.update(unit_id=None)
        for k in ("is_slep_staff", "unit_id", "rbd", "positions"):
            if k in changes:
                merged[k] = changes[k]
        try:
            check_mode(merged["is_slep_staff"], merged["unit_id"], merged["rbd"], merged["positions"])
        except ValueError as exc:
            raise UserInvalid([{"field": "_", "code": "invalid_combination", "message": str(exc)}])

        errs = []
        if merged["unit_id"] and merged["unit_id"] != str(current.get("unit_id") or ""):
            if merged["unit_id"] not in await units_service.get_active_ids([merged["unit_id"]]):
                errs.append({"field": "unit_id", "code": "unit_not_found", "message": "La unidad no existe o está inactiva"})
        if merged["rbd"] and merged["rbd"] != current.get("rbd"):
            if merged["rbd"] not in await establishments_service.existing_rbds([merged["rbd"]]):
                errs.append({"field": "rbd", "code": "rbd_not_found", "message": f"El establecimiento con RBD {merged['rbd']} no existe"})
        if errs:
            raise UserInvalid(errs)

        to_set = {k: v for k, v in changes.items() if k not in ("is_slep_staff", "unit_id", "rbd", "positions")}
        to_set.update(is_slep_staff=merged["is_slep_staff"], unit_id=_oid(merged["unit_id"]),
                      rbd=merged["rbd"], positions=merged["positions"])
        to_set.update(updated_at=_utcnow(), updated_by=_oid(actor_id))
        try:
            await db_service.db.users.update_one({"_id": current["_id"]}, {"$set": to_set})
        except DuplicateKeyError:
            raise UserConflict("Ya existe un usuario con ese correo", "duplicate", field="email")
        return await self.find_by_id(user_id)

    async def update_self(self, user_id: str, data: UserSelfUpdate) -> dict:
        """C19: solo teléfono y anexo. El tipo `UserSelfUpdate` ya hace imposible tocar otra cosa."""
        current = await self._load(user_id)
        changes = {k: v for k, v in data.model_dump().items() if v is not None}
        if changes:
            changes["updated_at"] = _utcnow()
            changes["updated_by"] = current["_id"]
            await db_service.db.users.update_one({"_id": current["_id"]}, {"$set": changes})
        return await self.find_by_id(user_id)

    # ══ Estado (soft delete, C9) ═══════════════════════════════════════════════
    async def _count_other_active_iam_admins(self, exclude_id) -> int:
        return await db_service.db.users.count_documents({
            "_id": {"$ne": exclude_id}, "status": "active",
            "access": {"$elemMatch": {"platform_id": "iam", "role": "admin"}}})

    async def disable(self, user_id: str, actor_id: Optional[str]) -> dict:
        current = await self._load(user_id)
        if current["status"] == "disabled":
            return await self.find_by_id(user_id)
        if str(current["_id"]) == str(actor_id) and _is_iam_admin(current):
            raise UserConflict("Un admin global no puede desactivarse a sí mismo", "self_disable")
        if current["status"] == "active" and _is_iam_admin(current) \
                and await self._count_other_active_iam_admins(current["_id"]) == 0:
            raise UserConflict("No se puede desactivar al último admin global activo", "last_admin")
        now = _utcnow()
        await db_service.db.users.update_one({"_id": current["_id"]}, {"$set": {
            "status": "disabled", "disabled_at": now, "updated_at": now, "updated_by": _oid(actor_id)}})
        await units_service.clear_head_for_user(str(current["_id"]))     # Q8
        return await self.find_by_id(user_id)

    async def enable(self, user_id: str, actor_id: Optional[str]) -> dict:
        """Reactiva: `active` si tiene contraseña o Google vinculado; si no, `invited` (A4)."""
        current = await self._load(user_id)
        if current["status"] != "disabled":
            return await self.find_by_id(user_id)
        new_status = "active" if _has_credential(current) else "invited"
        now = _utcnow()
        await db_service.db.users.update_one({"_id": current["_id"]}, {"$set": {
            "status": new_status, "disabled_at": None, "updated_at": now, "updated_by": _oid(actor_id)}})
        return await self.find_by_id(user_id)

    # ══ Accesos por plataforma ═════════════════════════════════════════════════
    async def set_access(self, user_id: str, platform_id: str, role: str, actor_id: Optional[str]) -> dict:
        current = await self._load(user_id)
        roles = await platforms_service.allowed_roles(platform_id)
        if roles is None:
            raise UserNotFound(f"Platform {platform_id} not found")
        if role not in roles:
            raise UserInvalid([{"field": "role", "code": "invalid_role",
                                "message": f"El rol '{role}' no existe en la plataforma '{platform_id}' (válidos: {', '.join(roles)})"}])
        now = _utcnow()
        entry = {"platform_id": platform_id, "role": role, "granted_at": now, "granted_by": _oid(actor_id)}
        access = [a for a in current.get("access", []) if a.get("platform_id") != platform_id] + [entry]
        await db_service.db.users.update_one({"_id": current["_id"]}, {"$set": {
            "access": access, "updated_at": now, "updated_by": _oid(actor_id)}})
        return await self.find_by_id(user_id)

    async def revoke_access(self, user_id: str, platform_id: str, actor_id: Optional[str]) -> dict:
        current = await self._load(user_id)
        if platform_id == "iam" and _is_iam_admin(current) and current["status"] == "active" \
                and await self._count_other_active_iam_admins(current["_id"]) == 0:
            raise UserConflict("No se puede quitar iam/admin al último admin global activo", "last_admin")
        access = [a for a in current.get("access", []) if a.get("platform_id") != platform_id]
        now = _utcnow()
        await db_service.db.users.update_one({"_id": current["_id"]}, {"$set": {
            "access": access, "updated_at": now, "updated_by": _oid(actor_id)}})
        return await self.find_by_id(user_id)

    # ══ Sesión y credenciales (las usa `auth`, nunca al revés) ═════════════════
    async def touch_login(self, user_id: str) -> None:
        await db_service.db.users.update_one({"_id": _oid(user_id)}, {"$set": {"last_login_at": _utcnow()}})

    async def touch_activity(self, user: dict) -> bool:
        """Escribe `last_activity_at` como máximo una vez por ACTIVITY_THROTTLE. El dato sale del
        documento ya leído (sin consulta extra) y el update condicional evita la doble escritura
        entre workers. Un fallo se registra y no rompe la request."""
        now = _utcnow()
        last = user.get("last_activity_at")
        if last is not None and now - last < ACTIVITY_THROTTLE:
            return False
        try:
            threshold = now - ACTIVITY_THROTTLE
            result = await db_service.db.users.update_one(
                {"_id": _oid(user["_id"]), "$or": [{"last_activity_at": None}, {"last_activity_at": {"$lt": threshold}}]},
                {"$set": {"last_activity_at": now}})
            return result.modified_count > 0
        except Exception:
            logger.exception("No se pudo registrar last_activity_at")
            return False

    async def set_local_password(self, user_id: str, hashed: str, must_change: bool = False,
                                 activate_invited: bool = False) -> dict:
        """Guarda la contraseña (ya hasheada por `auth`) y fija `password_changed_at`, lo que
        invalida todas las sesiones anteriores. Agrega el proveedor local si no existía."""
        current = await self._load(user_id)
        now = _utcnow()
        providers = [p for p in current.get("auth_providers", []) if p.get("provider") != "local"]
        providers.insert(0, {"provider": "local", "hashed_password": hashed,
                             "password_changed_at": now, "must_change_password": must_change})
        fields = {"auth_providers": providers, "updated_at": now}
        if activate_invited and current["status"] == "invited":
            fields["status"] = "active"
        await db_service.db.users.update_one({"_id": current["_id"]}, {"$set": fields})
        return await self.find_by_id(user_id)

    # ══ Bootstrap del admin (R6: mismo pipeline que cualquier alta) ════════════
    async def ensure_bootstrap_admin(self, email: str, make_hash: Callable[[], str]) -> None:
        """Garantiza el admin global. Idempotente y tolerante a la carrera de 2 workers.

        - Ya existe un usuario con ese correo -> no hace nada.
        - Existe el admin legado `{username, hashed_password, role}` sin correo -> se migra en
          el mismo `_id` conservando el hash (el login con la contraseña de siempre sigue
          funcionando) y los campos legados, de modo que volver al código anterior también
          funciona (rollback).
        - Si no, se crea con ADMIN_PASSWORD y `must_change_password`.
        """
        users = db_service.db.users
        if await users.find_one({"email": email}) is not None:
            return
        unit = await units_service.find_by_code(BOOTSTRAP_ADMIN_UNIT_CODE) or await units_service.find_by_code("DE")
        if unit is None:
            raise RuntimeError("No hay unidades: ensure_bootstrap_units() debe correr antes que el admin")
        now = _utcnow()
        admin_access = [
            {"platform_id": "iam", "role": "admin", "granted_at": now, "granted_by": None},
            {"platform_id": "datos", "role": "admin", "granted_at": now, "granted_by": None},
        ]
        legacy = await users.find_one({"username": "admin", "email": {"$exists": False}})
        try:
            if legacy is not None:
                first, _, last = (legacy.get("full_name") or "Administrador SLEP").partition(" ")
                await users.update_one({"_id": legacy["_id"]}, {"$set": {
                    "email": email, "first_name": first, "last_name": last or "SLEP",
                    "personal_phone": None, "work_extension": None,
                    "is_slep_staff": True, "unit_id": ObjectId(unit["_id"]), "rbd": None, "positions": [],
                    "status": "active",
                    "auth_providers": [{"provider": "local", "hashed_password": legacy["hashed_password"],
                                        "password_changed_at": None, "must_change_password": False}],
                    "access": admin_access, "invitation": None,
                    "last_login_at": None, "last_activity_at": None,
                    "created_at": now, "created_by": None, "updated_at": now, "updated_by": None, "disabled_at": None}})
                logger.info("Admin legado migrado al modelo de usuarios")
                return
            result = await self.create_many(
                [{"email": email, "first_name": "Administrador", "last_name": "SLEP",
                  "is_slep_staff": True, "unit_id": unit["_id"]}],
                actor_id=None, status="active", local_password_hash=make_hash(), must_change_password=True)
            row = result["items"][0]
            if row["status"] == "created":
                await users.update_one({"_id": ObjectId(row["id"])}, {"$set": {"access": admin_access}})
                logger.info("Admin global creado")
            elif row["status"] != "duplicate":
                raise RuntimeError(f"No se pudo crear el admin sembrado: {row['errors']}")
        except DuplicateKeyError:
            logger.info("Admin ya creado por otro worker")

    # ── interno ───────────────────────────────────────────────────────────────
    async def _load(self, user_id: str) -> dict:
        """Documento crudo (con ObjectId). Un id mal formado es 'no encontrado', no un 500 (D12)."""
        oid = _oid(user_id)
        doc = await db_service.db.users.find_one({"_id": oid}) if oid else None
        if doc is None:
            raise UserNotFound(f"User {user_id} not found")
        return doc


users_service = UsersService()
