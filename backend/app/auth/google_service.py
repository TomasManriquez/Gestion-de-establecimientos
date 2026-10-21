"""Inicio de sesión con Google Identity Services (C24, ADR-015).

El navegador entrega un `id_token` (`credential`); aquí se verifica y se resuelve a una persona. La
sesión la emite el controller con el mismo `_issue_token` del login con contraseña: este módulo no
emite nada. Todo fallo es un `GoogleLoginError` con un código interno; hacia afuera siempre es el
mismo 401, y el `credential` jamás se escribe en un log.
"""
import asyncio
import logging
import time
from typing import Optional

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.audit.audit_entity import AuditAction
from app.config import settings
from app.users.users_service import users_service

logger = logging.getLogger("auth.google")

GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")
GOOGLE_PROVIDER = "google"
CLOCK_SKEW_SECONDS = 10          # mismo motivo que `leeway` en get_current_user (D28: reloj de WSL2)
MAX_TOKEN_AGE_SECONDS = 5 * 60   # acota la reutilización de un id_token robado sin guardar estado
SYSTEM_ACTOR = "system:google"
NAME_MAX = 80
MAX_CREDENTIAL_LENGTH = 8192      # un id_token de Google mide ~1 a 2 KB


class GoogleLoginError(Exception):
    """Cualquier motivo por el que el login con Google no procede. `reason` es solo para el log del servidor."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _verify_signature(credential: str) -> dict:
    """Síncrono (descarga los certificados de Google). Comprueba firma, `aud` y `exp`."""
    return id_token.verify_oauth2_token(
        credential, google_requests.Request(), settings.GOOGLE_CLIENT_ID, clock_skew_in_seconds=CLOCK_SKEW_SECONDS)


class GoogleLoginService:
    async def verify(self, credential: str) -> dict:
        if not settings.GOOGLE_CLIENT_ID:
            raise GoogleLoginError("client_id_not_configured")
        if len(credential) > MAX_CREDENTIAL_LENGTH:
            raise GoogleLoginError("credential_too_long")
        try:
            claims = await asyncio.to_thread(_verify_signature, credential)
        except Exception:  # noqa: BLE001  firma, aud, exp, formato o red: todo es un rechazo
            raise GoogleLoginError("token_rejected")
        self.check_claims(claims)
        return claims

    @staticmethod
    def check_claims(claims: dict, now: Optional[float] = None) -> None:
        """Lo que la librería no comprueba por nosotros (o que se revisa de forma explícita)."""
        now = time.time() if now is None else now
        if claims.get("iss") not in GOOGLE_ISSUERS:
            raise GoogleLoginError("bad_issuer")
        if claims.get("email_verified") is not True:
            raise GoogleLoginError("email_not_verified")
        email = claims.get("email")
        if not isinstance(email, str) or "@" not in email:
            raise GoogleLoginError("no_email")
        domain = email.strip().lower().rpartition("@")[2]
        hd = claims.get("hd")
        if not isinstance(hd, str) or hd.lower() not in settings.ALLOWED_EMAIL_DOMAINS or hd.lower() != domain:
            raise GoogleLoginError("domain_not_allowed")       # `hd` ausente = cuenta personal de Gmail
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise GoogleLoginError("no_subject")
        iat = claims.get("iat")
        if not isinstance(iat, (int, float)) or isinstance(iat, bool) or iat > now + CLOCK_SKEW_SECONDS \
                or now - iat > MAX_TOKEN_AGE_SECONDS:
            raise GoogleLoginError("token_too_old")

    async def resolve_user(self, claims: dict) -> dict:
        """Persona que corresponde al token: por (google, subject); si no, por correo. Devuelve una
        cuenta `active` o lanza `GoogleLoginError`. El rol nunca sale del token."""
        subject = claims["sub"]
        email = claims["email"].strip().lower()

        user = await users_service.find_by_google_subject(subject)
        if user is None:
            user = await users_service.find_by_login(email)
            if user is None:
                user = await self._autoprovision(claims, email)       # lanza si está apagada
            if user["status"] == "disabled":
                raise GoogleLoginError("disabled")
            if not any(p.get("provider") == GOOGLE_PROVIDER and p.get("subject") == subject
                       for p in user.get("auth_providers", [])):
                if any(p.get("provider") == GOOGLE_PROVIDER for p in user.get("auth_providers", [])):
                    raise GoogleLoginError("linked_to_other_subject")
                user = await users_service.link_google(user, subject)
                if user is None:
                    raise GoogleLoginError("link_failed")
        if user["status"] != "active":
            raise GoogleLoginError("not_active")
        return user

    async def _autoprovision(self, claims: dict, email: str) -> dict:
        """Alta como lector de `datos`, sin asignar (G1, G2). Pasa por el pipeline de `users_service`:
        no hay una segunda ruta de creación. Si dos logins del mismo correo nuevo corren a la vez, el
        índice único hace que uno cree y el otro encuentre la cuenta ya creada."""
        if not settings.GOOGLE_AUTO_PROVISION:
            raise GoogleLoginError("no_account")
        local_part = email.partition("@")[0]
        item = {"email": email,
                "first_name": (str(claims.get("given_name") or "").strip() or local_part)[:NAME_MAX],
                "last_name": (str(claims.get("family_name") or "").strip() or "(sin apellido)")[:NAME_MAX],
                "is_slep_staff": None}
        result = await users_service.create_many(
            [item], SYSTEM_ACTOR, status="active", unassigned=True,
            auth_providers=[{"provider": GOOGLE_PROVIDER, "subject": claims["sub"], "linked_at": users_service.now()}],
            access=[{"platform_id": "datos", "role": "viewer", "granted_at": users_service.now(), "granted_by": None}],
            audit_action=AuditAction.USER_AUTOPROVISION)
        row = result["items"][0]
        if row["status"] == "created":
            return await users_service.find_by_id(row["id"])
        if row["status"] == "duplicate":                              # carrera: la otra petición ya la creó
            existing = await users_service.find_by_login(email)
            if existing is not None:
                return existing
        raise GoogleLoginError("provision_failed")


google_login_service = GoogleLoginService()
