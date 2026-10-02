import time
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.auth.auth_entity import AccessContext
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


class AuthService:
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        try:
            return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
        except Exception:
            return False

    def get_password_hash(self, password: str) -> str:
        salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

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
