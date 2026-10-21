"""
mail_service.py — envío de correo (ADR-012). Infraestructura, no dominio.

Un único método público, `send(to, subject, html, text)`. No hay endpoint que lo exponga: lo
invoca el código de dominio (alta, reenvío y restablecimiento) con el correo tomado del
documento del usuario, para que la casilla del SLEP no sea un relay abierto.

Dos modos (`MAIL_MODE`):
  - `gmail`   : Gmail API (`users.messages.send`) con el refresh token de la casilla remitente.
                El access token se renueva con una petición a `oauth2.googleapis.com/token`.
  - `console` : escribe el mensaje, con su enlace, en el log. Solo desarrollo (la configuración
                rechaza este modo si PUBLIC_BASE_URL no es localhost).

Los errores son `MailError` con un `code` estable que se guarda en `users.invitation.last_error`.
Nunca llevan el cuerpo de la respuesta de Google ni credenciales.
"""
import asyncio
import base64
import logging
import time
from email.message import EmailMessage
from typing import Optional

import httpx

from app.config import Settings, settings as default_settings

logger = logging.getLogger("mail")

TOKEN_URL = "https://oauth2.googleapis.com/token"
SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.send"
HTTP_TIMEOUT = httpx.Timeout(20.0, connect=10.0)
TOKEN_SKEW_SECONDS = 60


class MailError(Exception):
    """Fallo de envío. `code` es estable y apto para mostrarse al admin; el mensaje, no."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class MailService:
    def __init__(self, cfg: Optional[Settings] = None, transport: Optional[httpx.AsyncBaseTransport] = None):
        self._cfg = cfg or default_settings
        self._transport = transport
        self._access_token: Optional[str] = None
        self._expires_at: float = 0.0
        self._lock = asyncio.Lock()

    async def send(self, to: str, subject: str, html: str, text: str) -> None:
        for value in (to, subject):
            if "\r" in value or "\n" in value:
                raise MailError("invalid_message")
        if self._cfg.MAIL_MODE == "console":
            logger.info("[MAIL console] to=%s subject=%s\n%s", to, subject, text)
            return
        message = EmailMessage()
        message["From"] = self._cfg.GMAIL_SENDER_ADDRESS
        message["To"] = to
        message["Subject"] = subject
        message.set_content(text)
        message.add_alternative(html, subtype="html")
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, transport=self._transport) as client:
                for attempt in (1, 2):
                    token = await self._token(client, force=attempt == 2)
                    response = await client.post(
                        SEND_URL, json={"raw": raw}, headers={"Authorization": f"Bearer {token}"}
                    )
                    if response.status_code == 401 and attempt == 1:
                        continue  # el access token pudo caducar o revocarse: renovar una vez
                    break
        except httpx.TimeoutException:
            logger.error("Gmail: tiempo de espera agotado al enviar a %s", to)
            raise MailError("mail_timeout")
        except httpx.HTTPError as exc:
            logger.error("Gmail: error de red (%s)", type(exc).__name__)
            raise MailError("mail_send_failed")
        if response.status_code == 401:
            raise MailError("mail_auth_failed")
        if response.status_code >= 400:
            logger.error("Gmail rechazó el envío: HTTP %s", response.status_code)
            raise MailError("mail_send_failed")

    async def _token(self, client: httpx.AsyncClient, force: bool = False) -> str:
        async with self._lock:
            if not force and self._access_token and time.monotonic() < self._expires_at:
                return self._access_token
            response = await client.post(TOKEN_URL, data={
                "client_id": self._cfg.GOOGLE_CLIENT_ID,
                "client_secret": self._cfg.GOOGLE_CLIENT_SECRET,
                "refresh_token": self._cfg.GMAIL_REFRESH_TOKEN,
                "grant_type": "refresh_token",
            })
            if response.status_code != 200:
                # `invalid_grant`: el consentimiento se revocó (por ejemplo, cambió la clave de la casilla).
                error = ""
                try:
                    error = str(response.json().get("error", ""))
                except ValueError:
                    pass
                logger.critical("Gmail: no se pudo renovar el access token (HTTP %s, error=%s). "
                                "Repetir el consentimiento de la casilla remitente (07 §9).", response.status_code, error)
                self._access_token = None
                raise MailError("mail_auth_failed")
            payload = response.json()
            self._access_token = payload["access_token"]
            self._expires_at = time.monotonic() + max(int(payload.get("expires_in", 3600)) - TOKEN_SKEW_SECONDS, 0)
            return self._access_token


mail_service = MailService()
