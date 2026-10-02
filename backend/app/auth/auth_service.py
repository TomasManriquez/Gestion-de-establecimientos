import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.auth.auth_entity import AccessContext, COMMON_PASSWORDS, CONTEXT_WORDS, SEQUENCES
from app.config import settings
from app.users.users_service import users_service

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
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.ALGORITHM])
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
