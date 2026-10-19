import hashlib
import logging
import math
import re
import secrets
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional, Tuple

import bcrypt
import jwt
from bson import ObjectId
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.audit.audit_entity import AuditAction, AuditTarget
from app.audit.audit_service import audit_service
from app.auth.auth_entity import (AccessContext, COMMON_PASSWORDS, CONTEXT_WORDS, INVITE_TTL_HOURS, InvalidLink,
                                  PURPOSE_INVITE, PURPOSE_RESET, PasswordPolicyError, RESET_TTL_HOURS, RateLimited, SEQUENCES,
                                  SET_PASSWORD_PATH, render_invitation, render_password_reset)
from app.config import settings
from app.database.database_service import db_service
from app.mail.mail_service import MailError, mail_service
from app.users.users_service import users_service

logger = logging.getLogger("auth")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Costo de bcrypt. Los tests lo bajan para no pagar ~0.25 s por hash.
BCRYPT_ROUNDS = 12
# Hash de relleno: verificar contra algo aunque el usuario no exista iguala el tiempo de
# respuesta y evita enumerar cuentas por latencia.
_DUMMY_HASH = bcrypt.hashpw(b"dummy-password-for-timing", bcrypt.gensalt(rounds=4)).decode()

CREDENTIALS_EXCEPTION_DETAIL = "Could not validate credentials"


def _credentials_exception() -> HTTPException:
    """Un único 401 para cualquier fallo: no se distingue el motivo hacia afuera."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=CREDENTIALS_EXCEPTION_DETAIL,
        headers={"WWW-Authenticate": "Bearer"},
    )


def local_provider(user: dict) -> Optional[dict]:
    for p in user.get("auth_providers", []):
        if p.get("provider") == "local":
            return p
    return None


BCRYPT_MAX_BYTES = 72     # bcrypt 5 lanza ValueError sobre 72 bytes: se rechaza con 422, no 500


def normalize_password(password: str) -> str:
    """NFKC antes de validar y hashear (NIST: normalizar Unicode para que el mismo texto
    escrito con distinto teclado produzca el mismo hash)."""
    return unicodedata.normalize("NFKC", password)


class AuthService:
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Prueba la contraseña normalizada y, si difiere, la cruda (hashes anteriores a NFKC)."""
        candidates = {normalize_password(plain_password), plain_password}
        for candidate in candidates:
            data = candidate.encode("utf-8")
            if len(data) > BCRYPT_MAX_BYTES:
                continue
            try:
                if bcrypt.checkpw(data, hashed_password.encode("utf-8")):
                    return True
            except Exception:
                continue
        return False

    def get_password_hash(self, password: str) -> str:
        data = normalize_password(password).encode("utf-8")
        if len(data) > BCRYPT_MAX_BYTES:
            raise ValueError("password exceeds 72 bytes")      # la política lo rechaza antes
        return bcrypt.hashpw(data, bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("utf-8")

    def check_password_policy(self, password: str, email: Optional[str] = None) -> list:
        """Única función de política: la usan el cambio propio, el canje del enlace y el bootstrap
        (C17). Devuelve las infracciones como [{code, message}]; lista vacía = cumple."""
        pw = normalize_password(password)
        violations = []

        def add(code, message):
            violations.append({"code": code, "message": message})

        if len(pw) < settings.PASSWORD_MIN_LENGTH:
            add("min_length", f"Debe tener al menos {settings.PASSWORD_MIN_LENGTH} caracteres")
        if len(pw) > settings.PASSWORD_MAX_LENGTH:
            add("max_length", f"No puede superar {settings.PASSWORD_MAX_LENGTH} caracteres")
        if len(pw.encode("utf-8")) > BCRYPT_MAX_BYTES:
            add("max_bytes", f"No puede superar {BCRYPT_MAX_BYTES} bytes (los acentos ocupan más de uno)")
        if settings.PASSWORD_REQUIRE_CHAR_CLASSES:
            classes = sum([bool(re.search(r"[a-záéíóúñü]", pw)), bool(re.search(r"[A-ZÁÉÍÓÚÑÜ]", pw)),
                           bool(re.search(r"[0-9]", pw)), bool(re.search(r"[^\w\s]|_", pw))])
            if classes < settings.PASSWORD_REQUIRE_CHAR_CLASSES:
                add("char_classes", f"Debe combinar al menos {settings.PASSWORD_REQUIRE_CHAR_CLASSES} tipos de caracteres")
        folded = re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", pw.lower()).encode("ascii", "ignore").decode())
        # Lista de bloqueo (NIST: comunes, esperadas o comprometidas). Además de la coincidencia
        # exacta, se bloquea la palabra común con sufijo numérico ("password1234567"), las
        # secuencias y lo casi sin variedad ("aaaaaaaaaaaaaaa"), que es lo que se prueba primero.
        base = folded.rstrip("0123456789")
        if (pw.lower() in COMMON_PASSWORDS or folded in COMMON_PASSWORDS or (base and base in COMMON_PASSWORDS)
                or (folded and len(set(folded)) <= 3) or (len(folded) >= 8 and any(folded in seq for seq in SEQUENCES))):
            add("common_password", "Es una contraseña demasiado común o predecible")
        context = list(CONTEXT_WORDS)
        local = (email or "").partition("@")[0].lower()
        if len(local) >= 4:
            context.append(local)
            # También sin separadores: "ana.perez" -> "anaperez" (lo que la gente escribe en realidad)
            plain_local = re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", local).encode("ascii", "ignore").decode())
            if len(plain_local) >= 4:
                context.append(plain_local)
        if any(w in folded or w in pw.lower() for w in context):
            add("context_word", "No puede contener tu correo ni el nombre de la institución")
        return violations

    async def authenticate_user(self, login: str, password: str) -> Optional[dict]:
        """Correo (normalizado) o username legado. Solo entra quien está `active` y tiene
        contraseña local. Cualquier otro caso responde igual que una contraseña errónea."""
        user = await users_service.find_by_login(login)
        provider = local_provider(user) if user else None
        stored_hash = provider.get("hashed_password") if provider else None
        if user is None or user.get("status") != "active" or not stored_hash:
            self.verify_password(password, _DUMMY_HASH)
            return None
        if not self.verify_password(password, stored_hash):
            return None
        await users_service.touch_login(user["_id"])
        return user

    # ══ Rate limiting (ADR-014) ═════════════════════════════════════════════════════════════
    # Ventana fija con contadores en `rate_limits` (índice único por `key` y TTL en `expires_at`),
    # compartidos entre los workers de Gunicorn. Sin Redis. Si el almacén falla, el limitador no
    # bloquea (fail-open) y lo deja en ERROR: la autenticación depende de esa misma base.
    @staticmethod
    def rate_key(scope: str, *parts: str) -> str:
        """Clave opaca: lo que escribió el cliente (correo, token) se guarda solo como hash."""
        digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]
        return f"{scope}:{digest}"

    async def rate_guard(self, checks: list) -> None:
        """`checks` = [(clave, límite)]. Lanza `RateLimited` si alguno ya llegó a su límite."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        worst = 0
        try:
            for key, limit in checks:
                doc = await db_service.db.rate_limits.find_one({"key": key, "expires_at": {"$gt": now}})
                if doc is not None and doc.get("count", 0) >= limit:
                    worst = max(worst, math.ceil((doc["expires_at"] - now).total_seconds()))
        except Exception:  # noqa: BLE001
            logger.error("rate_limits no disponible: el límite no se aplicó", exc_info=True)
            return
        if worst:
            raise RateLimited(max(worst, 1))

    async def rate_hit(self, key: str, window_seconds: int) -> int:
        """Suma 1 al contador de la clave (abre la ventana si no hay una vigente). Devuelve el conteo."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        col = None
        try:
            col = db_service.db.rate_limits
            doc = await col.find_one_and_update({"key": key, "expires_at": {"$gt": now}}, {"$inc": {"count": 1}},
                                                return_document=ReturnDocument.AFTER)
            if doc is not None:
                return doc["count"]
            try:
                await col.update_one({"key": key}, {"$set": {"count": 1, "expires_at": now + timedelta(seconds=window_seconds)}},
                                     upsert=True)
            except DuplicateKeyError:            # otro worker abrió la ventana a la vez: sumar a la suya
                doc = await col.find_one_and_update({"key": key}, {"$inc": {"count": 1}}, return_document=ReturnDocument.AFTER)
                return doc["count"] if doc else 1
            return 1
        except Exception:  # noqa: BLE001
            logger.error("rate_limits no disponible: el intento no se contó", exc_info=True)
            return 0

    async def rate_clear(self, key: str) -> None:
        try:
            await db_service.db.rate_limits.delete_many({"key": key})
        except Exception:  # noqa: BLE001
            logger.error("rate_limits no disponible: no se pudo limpiar el contador", exc_info=True)

    # ══ Enlaces de un solo uso: invitación y restablecimiento (ADR-012) ═══════════════════
    @staticmethod
    def hash_token(raw: str) -> str:
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    async def issue_link_token(self, user_id: str, purpose: str, created_by: Optional[str]) -> Tuple[str, datetime]:
        """Emite un token nuevo e invalida el anterior del mismo usuario y propósito.

        Hay un único documento por (user_id, purpose) y se reemplaza con un upsert: la
        invalidación del anterior y la emisión del nuevo son la misma operación atómica. La base
        guarda solo el sha256; el token viaja una sola vez, en el correo.
        """
        raw = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        expires = now + timedelta(hours=INVITE_TTL_HOURS if purpose == PURPOSE_INVITE else RESET_TTL_HOURS)
        key = {"user_id": ObjectId(user_id), "purpose": purpose}
        fields = {"token_hash": self.hash_token(raw), "expires_at": expires, "used_at": None,
                  "created_by": ObjectId(created_by) if created_by else None, "created_at": now}
        try:
            await db_service.db.auth_tokens.update_one(key, {"$set": fields}, upsert=True)
        except DuplicateKeyError:        # dos emisiones simultáneas: la segunda reemplaza a la primera
            await db_service.db.auth_tokens.update_one(key, {"$set": fields})
        return raw, expires

    @staticmethod
    def _redeemable(raw: str) -> dict:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        return {"token_hash": AuthService.hash_token(raw), "used_at": None, "expires_at": {"$gt": now}}

    @staticmethod
    def link_for(raw: str) -> str:
        # Token en el fragmento (#): no llega a los logs del servidor ni a la cabecera Referer.
        return f"{settings.PUBLIC_BASE_URL}{SET_PASSWORD_PATH}#token={raw}"

    async def send_invitation(self, user: dict, actor_id: Optional[str], bulk_id: Optional[str] = None) -> dict:
        """Emite el token, envía el correo y guarda el resultado en `users.invitation`.

        Un fallo de correo NO lanza ni revierte el alta: el usuario sigue `invited` y el motivo
        queda en `invitation.last_error` para que el admin reenvíe (ADR-012 §3).
        """
        raw, expires = await self.issue_link_token(user["_id"], PURPOSE_INVITE, actor_id)
        subject, html, text = render_invitation(user.get("first_name", ""), self.link_for(raw))
        error: Optional[str] = None
        try:
            await mail_service.send(user["email"], subject, html, text)
        except MailError as exc:
            error = exc.code
        except Exception:  # noqa: BLE001 — cualquier otro fallo tampoco debe tumbar el alta
            logger.exception("Fallo inesperado al enviar la invitación")
            error = "mail_send_failed"
        sent_at = None if error else datetime.now(timezone.utc).replace(tzinfo=None)
        await users_service.set_invitation(user["_id"], sent_at, None if error else expires, error)
        await audit_service.record(actor_id, AuditAction.USER_INVITE, AuditTarget.USER, str(user["_id"]),
                                   {"invitation": [None, error or "sent"]}, bulk_id)
        return {"sent": error is None, "last_error": error, "expires_at": None if error else expires}

    async def invite_many(self, users: list, actor_id: Optional[str], bulk_id: Optional[str] = None) -> list:
        """Invitaciones en serie (lotes de INVITE_BATCH_LIMIT en el llamador). Un fallo no corta el resto."""
        return [await self.send_invitation(u, actor_id, bulk_id) for u in users]

    async def send_password_reset(self, user: dict, actor_id: Optional[str]) -> datetime:
        """Restablecimiento iniciado por el admin: mismo mecanismo con `purpose: reset`. A diferencia
        de la invitación, aquí el correo ES la operación: si falla, se lanza `MailError`."""
        raw, expires = await self.issue_link_token(user["_id"], PURPOSE_RESET, actor_id)
        subject, html, text = render_password_reset(user.get("first_name", ""), self.link_for(raw))
        await mail_service.send(user["email"], subject, html, text)
        await audit_service.record(actor_id, AuditAction.USER_PASSWORD_RESET, AuditTarget.USER, str(user["_id"]),
                                   {"reset_link": [None, "sent"]})
        return expires

    async def redeem_link(self, raw_token: str, password: str) -> dict:
        """Canjea el enlace: valida la política, consume el token de forma atómica y fija la contraseña.

        `InvalidLink` ante cualquier problema con el enlace (mismo error para usado, vencido,
        inexistente o de un usuario que ya no está en el estado esperado). `PasswordPolicyError`
        NO consume el token: la persona puede corregir y reintentar con el mismo enlace.
        """
        token = await db_service.db.auth_tokens.find_one(self._redeemable(raw_token))
        if token is None:
            raise InvalidLink()
        user = await users_service.find_by_id(str(token["user_id"]))
        expected = {PURPOSE_INVITE: "invited", PURPOSE_RESET: "active"}[token["purpose"]]
        if user is None or user.get("status") != expected:
            raise InvalidLink()
        violations = self.check_password_policy(password, user.get("email"))
        if violations:
            raise PasswordPolicyError(violations)
        # Consumo atómico: solo una petición gana si dos canjean a la vez.
        consumed = await db_service.db.auth_tokens.find_one_and_update(
            self._redeemable(raw_token),
            {"$set": {"used_at": datetime.now(timezone.utc).replace(tzinfo=None)}},
            return_document=ReturnDocument.AFTER)
        if consumed is None:
            raise InvalidLink()
        updated = await users_service.set_local_password(
            user["_id"], self.get_password_hash(password), activate_invited=token["purpose"] == PURPOSE_INVITE)
        await audit_service.record(user["_id"], AuditAction.USER_PASSWORD_SET, AuditTarget.USER, user["_id"],
                                   {"via": [None, token["purpose"]]})
        return updated

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        to_encode = data.copy()
        now = datetime.now(timezone.utc)
        expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
        to_encode.update({"exp": expire, "iat": int(time.time())})
        return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.ALGORITHM)

    async def get_current_user(self, token: str = Depends(oauth2_scheme)) -> dict:
        """Verifica el token y vuelve a leer al usuario (el rol nunca se toma del token, 04 §1).

        401 si: firma o `exp` inválidos, `sub` ausente o malformado, usuario inexistente, usuario
        que no está `active`, o token emitido antes del último cambio de contraseña.
        """
        try:
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.ALGORITHM], leeway=10)
        except jwt.PyJWTError:
            raise _credentials_exception()
        sub = payload.get("sub")
        if not isinstance(sub, str) or not sub:
            raise _credentials_exception()

        user = await users_service.find_for_session(sub)
        if user is None or user.get("status") != "active":
            raise _credentials_exception()

        provider = local_provider(user)
        changed_at = provider.get("password_changed_at") if provider else None
        if changed_at is not None:
            # Comparación truncada al segundo: el token emitido en el mismo segundo del cambio es válido.
            cutoff = int(changed_at.replace(tzinfo=timezone.utc).timestamp())
            iat = payload.get("iat")
            if not isinstance(iat, (int, float)) or int(iat) < cutoff:
                raise _credentials_exception()

        await users_service.touch_activity(user)
        return user


auth_service = AuthService()


def rate_limited_http(exc: RateLimited) -> HTTPException:
    """429 con `Retry-After`. El mismo mensaje exista o no la cuenta."""
    minutes = max(1, math.ceil(exc.retry_after / 60))
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        detail={"code": "rate_limited", "message": f"Demasiados intentos. Espera {minutes} min e inténtalo de nuevo."},
        headers={"Retry-After": str(exc.retry_after)})


def client_ip(request) -> str:
    """IP del cliente según el servidor ASGI. En producción Gunicorn aplica `--forwarded-allow-ips`
    y `request.client.host` ya es la dirección real que nginx puso en X-Forwarded-For. Nunca se lee
    la cabecera a mano: cualquiera puede enviarla."""
    return request.client.host if request.client else "unknown"


def require_access(platform: Optional[str], roles: Optional[Iterable[str]] = None):
    """Dependencia de autorización (ADR-009).

    `require_access("datos", {"admin", "editor"})` exige un rol permitido en esa plataforma;
    `require_access(None)` solo exige un usuario autenticado y activo. Devuelve un
    `AccessContext`. 401 si la sesión no es válida; 403 si falta el rol.

    El rol sale del documento de usuario recién leído, no del token. Un rol desconocido en
    `access[]` no concede nada. La función lleva el atributo `__require_access__` para que un
    test pueda comprobar que toda ruta la declara (04 §9.2).
    """
    allowed = frozenset(roles) if roles is not None else None

    async def _dependency(user: dict = Depends(auth_service.get_current_user)) -> AccessContext:
        role = None
        if platform is not None:
            entry = next((a for a in user.get("access", []) if a.get("platform_id") == platform), None)
            role = entry.get("role") if entry else None
            if role is None or (allowed is not None and role not in allowed):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return AccessContext(user_id=str(user["_id"]), role=role, user=user)

    _dependency.__require_access__ = (platform, allowed)
    return _dependency
