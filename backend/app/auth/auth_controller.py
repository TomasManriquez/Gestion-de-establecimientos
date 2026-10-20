import logging
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from app.config import settings
from app.auth.auth_service import _credentials_exception, auth_service, client_ip, rate_limited_http, require_access
from app.auth.google_service import GoogleLoginError, google_login_service
from app.auth.auth_entity import (AccessContext, AccessSummary, AuthConfig, ChangePasswordRequest, GOOGLE_IP_LIMIT,
                                  GOOGLE_WINDOW_SECONDS, GoogleLoginRequest, InvalidLink, LoginRequest,
                                  LOGIN_ACCOUNT_LIMIT, LOGIN_IP_LIMIT, LOGIN_WINDOW_SECONDS, PLATFORM_DATOS, PasswordPolicy,
                                  PasswordPolicyError, REDEEM_IP_LIMIT, REDEEM_WINDOW_SECONDS, RateLimited,
                                  SetPasswordRequest, Token, UserResponse)
from app.users.users_entity import UserNotFound
from app.users.users_service import users_service

logger = logging.getLogger("auth")
router = APIRouter(prefix="/api/auth", tags=["auth"])


def _issue_token(user: dict) -> dict:
    """El `sub` es str(_id): estable, nunca el correo ni el username (C6)."""
    access_token = auth_service.create_access_token(
        data={"sub": str(user["_id"]), "role": datos_role(user) or "none"},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": access_token, "token_type": "bearer"}


def datos_role(user: dict):
    entry = next((a for a in user.get("access", []) if a.get("platform_id") == PLATFORM_DATOS), None)
    return entry.get("role") if entry else None


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def _limited_login(request: Request, login: str, password: str) -> dict:
    """Login con límite por (cuenta + IP) y por IP (ADR-014). Cuenta inexistente, desactivada o con
    clave errónea cuentan igual y responden igual, así que el límite no revela qué cuentas existen.
    El límite incluye la IP a propósito: un tercero no puede dejar inutilizable la cuenta de otro."""
    ip = client_ip(request)
    account_key = auth_service.rate_key("login-account", ip, login.strip().lower())
    ip_key = auth_service.rate_key("login-ip", ip)
    try:
        await auth_service.rate_guard([(account_key, LOGIN_ACCOUNT_LIMIT), (ip_key, LOGIN_IP_LIMIT)])
    except RateLimited as exc:
        raise rate_limited_http(exc)
    user = await auth_service.authenticate_user(login, password)
    if not user:
        await auth_service.rate_hit(account_key, LOGIN_WINDOW_SECONDS)
        await auth_service.rate_hit(ip_key, LOGIN_WINDOW_SECONDS)
        raise _unauthorized()
    await auth_service.rate_clear(account_key)
    return user


@router.post("/login", response_model=Token)
async def login_for_access_token(payload: LoginRequest, request: Request):
    """
    JSON Login endpoint. `username` acepta el correo o, mientras dure la compatibilidad, el
    username legado. Responde 429 con `Retry-After` al superar el límite de intentos fallidos.
    """
    return _issue_token(await _limited_login(request, payload.username, payload.password))

@router.get("/config", response_model=AuthConfig)
async def get_auth_config():
    """Pública: el frontend no tiene variables de entorno (ADR-008) y necesita el client id de Google
    para dibujar el botón antes de que haya sesión. El client id no es secreto."""
    return {"google_client_id": settings.GOOGLE_CLIENT_ID}


@router.post("/google", response_model=Token)
async def login_with_google(payload: GoogleLoginRequest, request: Request):
    """Login con Google Identity Services (C24). Pública. Todo fallo es el mismo 401 de las demás rutas,
    sin revelar la causa; el `credential` no se registra en ningún log. Los rechazos cuentan para el
    límite por IP (429 con `Retry-After`). La sesión sale de `_issue_token`, el único punto de emisión."""
    ip_key = auth_service.rate_key("google-ip", client_ip(request))
    try:
        await auth_service.rate_guard([(ip_key, GOOGLE_IP_LIMIT)])
    except RateLimited as exc:
        raise rate_limited_http(exc)
    try:
        claims = await google_login_service.verify(payload.credential)
        user = await google_login_service.resolve_user(claims)
    except GoogleLoginError as exc:
        logger.info("Login con Google rechazado: %s", exc.reason)
        await auth_service.rate_hit(ip_key, GOOGLE_WINDOW_SECONDS)
        raise _credentials_exception()
    await users_service.touch_login(user["_id"])
    return _issue_token(user)


@router.post("/login-form", response_model=Token)
async def login_for_access_token_form(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Form-url-encoded Login endpoint (standard for Swagger UI)
    """
    return _issue_token(await _limited_login(request, form_data.username, form_data.password))

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request):
    """Corta TODAS las sesiones de la persona (`sessions_revoked_at`): es la forma sin estado, no hay
    lista de tokens. Responde 204 aunque el token ya no sirva (vencido, revocado, malformado): cerrar
    sesión nunca falla para quien la cierra. Los 401 de esta ruta no los produce `require_access`."""
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() == "bearer" and token:
        try:
            user = await auth_service.get_current_user(token)
        except HTTPException:
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        await users_service.revoke_sessions(user["_id"])
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.get("/me", response_model=UserResponse)
async def read_users_me(ctx: AccessContext = Depends(require_access(None))):
    """Contrato original `{username, full_name, role}` más `id`, `email` y `access` (aditivo).
    `role` es el rol en `datos`, o "none" si el usuario no tiene acceso a esa plataforma."""
    user = ctx.user
    full_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or user.get("full_name", "")
    return {
        "username": user.get("username") or user.get("email") or "",
        "full_name": full_name,
        "role": datos_role(user) or "none",
        "id": str(user["_id"]),
        "email": user.get("email"),
        "access": [AccessSummary(platform_id=a["platform_id"], role=a["role"]) for a in user.get("access", [])],
    }


@router.get("/password-policy", response_model=PasswordPolicy)
async def get_password_policy():
    """Pública: el frontend la necesita antes de que haya sesión (pantalla de definir contraseña).
    Solo expone los números de la política, nunca la lista de bloqueo."""
    return {"min_length": settings.PASSWORD_MIN_LENGTH, "max_length": settings.PASSWORD_MAX_LENGTH,
            "require_char_classes": settings.PASSWORD_REQUIRE_CHAR_CLASSES}


@router.post("/password", response_model=Token)
async def change_own_password(payload: ChangePasswordRequest, ctx: AccessContext = Depends(require_access(None))):
    """Cambio de contraseña propio (C19). Devuelve un token nuevo: el cambio fija
    `password_changed_at`, lo que invalida el token con el que se llamó.

    Una contraseña actual incorrecta responde 400, NUNCA 401: el interceptor del frontend
    (App.jsx) cierra la sesión ante cualquier 401.
    """
    user = ctx.user
    provider = next((p for p in user.get("auth_providers", []) if p.get("provider") == "local"), None)
    if provider is None or not provider.get("hashed_password"):
        raise HTTPException(status.HTTP_409_CONFLICT, detail={
            "code": "no_local_password",
            "message": "Esta cuenta no tiene contraseña local. Solicita un restablecimiento."})
    if not auth_service.verify_password(payload.current_password, provider["hashed_password"]):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={
            "code": "current_password_incorrect", "message": "La contraseña actual no es correcta"})
    violations = auth_service.check_password_policy(payload.new_password, user.get("email"))
    if violations:
        raise HTTPException(422, detail=violations)
    try:
        updated = await users_service.set_local_password(ctx.user_id, auth_service.get_password_hash(payload.new_password))
    except UserNotFound:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials",
                            headers={"WWW-Authenticate": "Bearer"})
    return _issue_token(updated)


@router.post("/set-password", status_code=status.HTTP_204_NO_CONTENT)
async def set_password(payload: SetPasswordRequest, request: Request):
    """Canje del enlace de invitación o de restablecimiento (pública: aún no hay sesión).

    Todo fallo del enlace responde el mismo 400, sin distinguir usado, vencido o inexistente. Una
    contraseña que incumple la política responde 422 y NO consume el enlace. No devuelve token:
    la persona entra después con su correo y la contraseña recién definida."""
    ip_key = auth_service.rate_key("redeem-ip", client_ip(request))
    try:
        await auth_service.rate_guard([(ip_key, REDEEM_IP_LIMIT)])
    except RateLimited as exc:
        raise rate_limited_http(exc)
    try:
        await auth_service.redeem_link(payload.token, payload.password)
    except InvalidLink:
        await auth_service.rate_hit(ip_key, REDEEM_WINDOW_SECONDS)       # adivinar enlaces cuesta intentos
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={
            "code": "invalid_or_expired_link",
            "message": "El enlace no es válido o ya venció. Pide a un administrador que te envíe uno nuevo."})
    except PasswordPolicyError as exc:
        raise HTTPException(422, detail=exc.violations)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
