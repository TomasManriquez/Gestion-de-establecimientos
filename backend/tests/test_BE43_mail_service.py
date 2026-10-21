"""
test_BE43_mail_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: US-14 · mail_service (ADR-012): modo console y modo gmail sin red real

Verifica que:
  - `console` escribe el mensaje (con su enlace) en el log y no hace ninguna petición
  - `gmail` renueva el access token, arma un mensaje multipart (texto + HTML) y llama a la API de Gmail
  - el access token se reutiliza hasta caducar; un 401 de Gmail renueva el token una vez y reintenta
  - cada fallo se traduce a un código estable (mail_auth_failed, mail_send_failed, mail_timeout)
  - un salto de línea en destinatario o asunto se rechaza (inyección de cabeceras)
  - ni el log ni la excepción contienen credenciales ni el cuerpo de la respuesta de Google
"""
import base64
import email
import email.header
import json
import logging
from urllib.parse import parse_qs

import httpx
import pytest

from app.config import Settings
from app.mail.mail_service import MailError, MailService, SEND_URL, TOKEN_URL

ENV = {
    "JWT_SECRET": "x" * 64, "ADMIN_PASSWORD": "una-clave-de-prueba",
    "ALLOWED_EMAIL_DOMAINS": "slepllanquihue.cl", "BOOTSTRAP_ADMIN_EMAIL": "admin@slepllanquihue.cl",
    "GOOGLE_AUTO_PROVISION": "false",
    "MAIL_MODE": "gmail", "PUBLIC_BASE_URL": "https://gestion.slepllanquihue.cl",
    "GMAIL_SENDER_ADDRESS": "no-responder@slepllanquihue.cl", "GMAIL_REFRESH_TOKEN": "1//refresh-token-secreto",
    "GOOGLE_CLIENT_ID": "id.apps.googleusercontent.com", "GOOGLE_CLIENT_SECRET": "GOCSPX-secreto-del-cliente",
}
SECRETS = ("1//refresh-token-secreto", "GOCSPX-secreto-del-cliente", "ya29.token-de-acceso")


class FakeGoogle:
    """Responde a /token y a /send; registra lo recibido. `send_codes` se consume en orden."""

    def __init__(self, token_status=200, send_codes=(200,), token_error="invalid_grant"):
        self.calls, self.token_status, self.send_codes, self.token_error = [], token_status, list(send_codes), token_error

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        if str(request.url) == TOKEN_URL:
            if self.token_status != 200:
                return httpx.Response(self.token_status, json={"error": self.token_error, "error_description": SECRETS[0]})
            return httpx.Response(200, json={"access_token": "ya29.token-de-acceso", "expires_in": 3600})
        assert str(request.url) == SEND_URL
        code = self.send_codes.pop(0) if self.send_codes else 200
        return httpx.Response(code, json={"id": "m1"} if code == 200 else {"error": {"message": SECRETS[2]}})

    def sends(self):
        return [c for c in self.calls if str(c.url) == SEND_URL]

    def tokens(self):
        return [c for c in self.calls if str(c.url) == TOKEN_URL]


def make(fake, **overrides):
    return MailService(Settings({**ENV, **overrides}), transport=httpx.MockTransport(fake))


async def deliver(service, to="ana.perez@slepllanquihue.cl"):
    await service.send(to, "Define tu contraseña", "<p>Hola <b>Ana</b></p>", "Hola Ana\nhttps://x/definir-contrasena#token=abc")


@pytest.mark.asyncio
async def test_BE43_console_logs_the_message_and_makes_no_request(caplog):
    fake = FakeGoogle()
    service = MailService(Settings({**ENV, "MAIL_MODE": "console", "PUBLIC_BASE_URL": "http://localhost:5173"}),
                          transport=httpx.MockTransport(fake))
    with caplog.at_level(logging.INFO, logger="mail"):
        await deliver(service)
    assert fake.calls == []
    assert "ana.perez@slepllanquihue.cl" in caplog.text
    assert "definir-contrasena#token=abc" in caplog.text


@pytest.mark.asyncio
async def test_BE43_gmail_refreshes_token_then_sends_multipart_message():
    fake = FakeGoogle()
    await deliver(make(fake))
    assert len(fake.tokens()) == 1 and len(fake.sends()) == 1
    form = parse_qs(fake.tokens()[0].content.decode())
    assert form["grant_type"] == ["refresh_token"] and form["refresh_token"] == ["1//refresh-token-secreto"]
    send = fake.sends()[0]
    assert send.headers["authorization"] == "Bearer ya29.token-de-acceso"
    msg = email.message_from_bytes(base64.urlsafe_b64decode(json.loads(send.content)["raw"]))
    assert msg["To"] == "ana.perez@slepllanquihue.cl"
    assert msg["From"] == "no-responder@slepllanquihue.cl"
    assert str(email.header.make_header(email.header.decode_header(msg["Subject"]))) == "Define tu contraseña"
    types = [p.get_content_type() for p in msg.walk() if not p.is_multipart()]
    assert types == ["text/plain", "text/html"]
    text = next(p for p in msg.walk() if p.get_content_type() == "text/plain").get_payload(decode=True).decode()
    assert "definir-contrasena#token=abc" in text


@pytest.mark.asyncio
async def test_BE43_access_token_is_reused_between_sends():
    fake = FakeGoogle()
    service = make(fake)
    await deliver(service)
    await deliver(service, "carla.soto@slepllanquihue.cl")
    assert len(fake.tokens()) == 1 and len(fake.sends()) == 2


@pytest.mark.asyncio
async def test_BE43_401_from_gmail_renews_token_once_and_retries():
    fake = FakeGoogle(send_codes=(401, 200))
    await deliver(make(fake))
    assert len(fake.tokens()) == 2 and len(fake.sends()) == 2


@pytest.mark.asyncio
async def test_BE43_persistent_401_is_auth_failed():
    fake = FakeGoogle(send_codes=(401, 401))
    with pytest.raises(MailError) as exc:
        await deliver(make(fake))
    assert exc.value.code == "mail_auth_failed" and len(fake.sends()) == 2


@pytest.mark.asyncio
async def test_BE43_revoked_consent_is_auth_failed_and_logged_critical(caplog):
    fake = FakeGoogle(token_status=400)
    with caplog.at_level(logging.CRITICAL, logger="mail"):
        with pytest.raises(MailError) as exc:
            await deliver(make(fake))
    assert exc.value.code == "mail_auth_failed"
    assert fake.sends() == []
    assert any(r.levelno == logging.CRITICAL for r in caplog.records)
    assert "invalid_grant" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 403, 429, 500, 503])
async def test_BE43_gmail_errors_map_to_send_failed(status):
    with pytest.raises(MailError) as exc:
        await deliver(make(FakeGoogle(send_codes=(status,))))
    assert exc.value.code == "mail_send_failed"


@pytest.mark.asyncio
async def test_BE43_timeout_and_network_errors_have_stable_codes():
    def boom(exc):
        def handler(request):
            raise exc
        return handler
    with pytest.raises(MailError) as e1:
        await deliver(MailService(Settings(ENV), transport=httpx.MockTransport(boom(httpx.ReadTimeout("t")))))
    assert e1.value.code == "mail_timeout"
    with pytest.raises(MailError) as e2:
        await deliver(MailService(Settings(ENV), transport=httpx.MockTransport(boom(httpx.ConnectError("c")))))
    assert e2.value.code == "mail_send_failed"


@pytest.mark.asyncio
@pytest.mark.parametrize("to,subject", [
    ("a@slepllanquihue.cl\r\nBcc: victima@x.cl", "Hola"), ("a@slepllanquihue.cl", "Hola\nBcc: x@x.cl"),
])
async def test_BE43_header_injection_is_rejected_before_any_request(to, subject):
    fake = FakeGoogle()
    with pytest.raises(MailError) as exc:
        await make(fake).send(to, subject, "<p>x</p>", "x")
    assert exc.value.code == "invalid_message" and fake.calls == []


@pytest.mark.asyncio
async def test_BE43_no_secret_in_exception_or_log(caplog):
    for fake in (FakeGoogle(token_status=400), FakeGoogle(send_codes=(500,)), FakeGoogle(send_codes=(401, 401))):
        with caplog.at_level(logging.DEBUG):
            with pytest.raises(MailError) as exc:
                await deliver(make(fake))
        assert not any(s in str(exc.value) or s in repr(exc.value) for s in SECRETS)
    assert not any(s in caplog.text for s in SECRETS)
