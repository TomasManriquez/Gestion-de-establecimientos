"""
vault_service.py — credenciales cifradas por establecimiento (ADR-021).

La contraseña se guarda con Fernet y la llave `VAULT_KEY`. Ningún método devuelve la contraseña salvo
`reveal`, que registra la entrega en `audit_log` ANTES de descifrar y falla cerrado: sin registro no sale
el secreto. El service no recibe al usuario (L3): el controller decide quién puede y cuántas veces.
"""
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from cryptography.fernet import Fernet, InvalidToken

from app.audit.audit_entity import AuditAction, AuditTarget
from app.audit.audit_service import audit_service, diff
from app.config import settings
from app.database.database_service import db_service
from app.vault.vault_entity import CredentialCreate, CredentialUpdate

_VISIBLE = ("name", "username", "url")      # campos que el log de cambios registra con su valor


class VaultError(Exception):
    """`audit_failed` (503: no se entregó nada) o `decrypt_failed` (500: llave distinta a la que cifró)."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _public(doc: dict) -> dict:
    """Documento sin `password_enc`: lo único que sale en listas, POST y PUT."""
    out = {k: v for k, v in doc.items() if k != "password_enc"}
    out["_id"] = str(doc["_id"])
    out["has_password"] = True
    return out


def _oid(value: str) -> Optional[ObjectId]:
    return ObjectId(value) if ObjectId.is_valid(value) and len(value) == 24 else None


class VaultService:
    @staticmethod
    def _fernet() -> Fernet:
        return Fernet(settings.VAULT_KEY.encode())

    async def list_for(self, rbd: str) -> list:
        return [_public(d) async for d in db_service.db.vault_credentials.find({"rbd": rbd}).sort("name", 1)]

    async def _find(self, rbd: str, cred_id: str) -> Optional[dict]:
        oid = _oid(cred_id)
        return None if oid is None else await db_service.db.vault_credentials.find_one({"_id": oid, "rbd": rbd})

    async def create(self, rbd: str, data: CredentialCreate, actor_id: str) -> dict:
        now = _now()
        doc = {"rbd": rbd, "name": data.name, "username": data.username, "url": data.url,
               "password_enc": self._fernet().encrypt(data.password.encode()).decode(),
               "created_by": actor_id, "created_at": now, "updated_by": actor_id, "updated_at": now}
        doc["_id"] = (await db_service.db.vault_credentials.insert_one(doc)).inserted_id
        await audit_service.record(actor_id, AuditAction.VAULT_CREATE, AuditTarget.VAULT, str(doc["_id"]),
                                   {"rbd": rbd, **{f: doc[f] for f in _VISIBLE}})
        return _public(doc)

    async def update(self, rbd: str, cred_id: str, data: CredentialUpdate, actor_id: str) -> Optional[dict]:
        before = await self._find(rbd, cred_id)
        if before is None:
            return None
        sent = data.model_dump(exclude_unset=True)
        sent = {k: v for k, v in sent.items() if v is not None or k in ("username", "url")}   # null borra solo opcionales
        password = sent.pop("password", None)
        fields = {**sent, "updated_by": actor_id, "updated_at": _now()}
        if password is not None:
            fields["password_enc"] = self._fernet().encrypt(password.encode()).decode()
        await db_service.db.vault_credentials.update_one({"_id": before["_id"]}, {"$set": fields})
        changes = diff(before, {**before, **fields}, _VISIBLE)
        if password is not None:
            changes["password_changed"] = True            # solo «cambió»: ni el valor nuevo ni el anterior
        await audit_service.record(actor_id, AuditAction.VAULT_UPDATE, AuditTarget.VAULT, str(before["_id"]),
                                   {"rbd": rbd, "name": fields.get("name", before["name"]), **changes})
        return _public({**before, **fields})

    async def delete(self, rbd: str, cred_id: str, actor_id: str) -> bool:
        before = await self._find(rbd, cred_id)
        if before is None:
            return False
        await db_service.db.vault_credentials.delete_one({"_id": before["_id"]})
        await audit_service.record(actor_id, AuditAction.VAULT_DELETE, AuditTarget.VAULT, str(before["_id"]),
                                   {"rbd": rbd, **{f: before.get(f) for f in _VISIBLE}})
        return True

    async def reveal(self, rbd: str, cred_id: str, actor_id: str) -> Optional[str]:
        """Contraseña en claro, o None si la credencial no existe. Orden fijo: buscar → auditar → descifrar."""
        doc = await self._find(rbd, cred_id)
        if doc is None:
            return None
        if not await audit_service.record(actor_id, AuditAction.VAULT_REVEAL, AuditTarget.VAULT, str(doc["_id"]),
                                          {"rbd": rbd, "name": doc["name"]}):
            raise VaultError("audit_failed")              # fail-closed: sin registro no hay entrega
        try:
            return self._fernet().decrypt(doc["password_enc"].encode()).decode()
        except InvalidToken:
            raise VaultError("decrypt_failed")


vault_service = VaultService()
