"""
test_BE43_mail_service.py
━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: US-14 · mail_service (ADR-012, ADR-017): modos console, gmail y smtp sin red real

Verifica que:
  - `console` escribe el mensaje (con su enlace) en el log y no hace ninguna petición
  - `gmail` renueva el access token, arma un mensaje multipart (texto + HTML) y llama a la API de Gmail
  - el access token se reutiliza hasta caducar; un 401 de Gmail renueva el token una vez y reintenta
  - `smtp` abre la conexión con TLS verificado (STARTTLS en 587, TLS implícito en 465), inicia sesión y envía
    un mensaje multipart, en un hilo aparte y sin tocar la API de Gmail
  - cada fallo se traduce a un código estable (mail_auth_failed, mail_send_failed, mail_timeout)
  - un salto de línea en destinatario o asunto se rechaza (inyección de cabeceras)
  - ni el log ni la excepción contienen credenciales ni el cuerpo de la respuesta del servidor
"""
import base64
import email
import email.header
import json
import logging
import smtplib
import ssl
import threading
from urllib.parse import parse_qs

import httpx
import pytest

from app.config import Settings
from app.mail import mail_service as mail_module
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


# ─── Modo smtp (ADR-017): un servidor SMTP falso sustituye a smtplib; no hay red real ───

SMTP_PASSWORD = "abcd efgh ijkl mnop"
SMTP_ENV = {
    "JWT_SECRET": "x" * 64, "ADMIN_PASSWORD": "una-clave-de-prueba",
    "ALLOWED_EMAIL_DOMAINS": "slepllanquihue.cl", "BOOTSTRAP_ADMIN_EMAIL": "admin@slepllanquihue.cl",
    "GOOGLE_AUTO_PROVISION": "false",
    "MAIL_MODE": "smtp", "PUBLIC_BASE_URL": "https://gestion.slepllanquihue.cl",
    "SMTP_HOST": "smtp.gmail.com", "SMTP_PORT": "587", "SMTP_USERNAME": "correos.automaticos@slepllanquihue.cl",
    "SMTP_PASSWORD": SMTP_PASSWORD, "SMTP_SENDER_ADDRESS": "correos.automaticos@slepllanquihue.cl",
}


class FakeSMTPServer:
    """Hace de `smtplib.SMTP` y de `SMTP_SSL`: registra el orden de las llamadas y puede fallar en cada paso."""

    def __init__(self, connect_error=None, starttls_error=None, login_error=None, send_error=None):
        self.connect_error, self.starttls_error, self.login_error, self.send_error = (
            connect_error, starttls_error, login_error, send_error)
        self.events, self.sent, self.login_thread = [], [], None

    def factory(self, kind):
        def build(host, port, timeout=None, context=None):
            if self.connect_error:
                raise self.connect_error
            self.events.append((kind, host, port, timeout, context))
            return self
        return build

    def install(self, monkeypatch):
        monkeypatch.setattr(mail_module.smtplib, "SMTP", self.factory("SMTP"))
        monkeypatch.setattr(mail_module.smtplib, "SMTP_SSL", self.factory("SMTP_SSL"))
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.events.append(("quit",))
        return False

    def starttls(self, context=None):
        if self.starttls_error:
            raise self.starttls_error
        self.events.append(("starttls", context))

    def login(self, user, password):
        self.login_thread = threading.get_ident()
        if self.login_error:
            raise self.login_error
        self.events.append(("login", user, password))

    def send_message(self, message):
        if self.send_error:
            raise self.send_error
        self.sent.append(message)
        self.events.append(("send",))

    def names(self):
        return [e[0] for e in self.events]


def make_smtp(server, monkeypatch, **overrides):
    server.install(monkeypatch)
    return MailService(Settings({**SMTP_ENV, **overrides}))


@pytest.mark.asyncio
async def test_BE43_smtp_starttls_login_and_send_in_order(monkeypatch):
    server = FakeSMTPServer()
    await deliver(make_smtp(server, monkeypatch))
    assert server.names() == ["SMTP", "starttls", "login", "send", "quit"]
    _, host, port, timeout, _ = server.events[0]
    assert (host, port) == ("smtp.gmail.com", 587) and timeout and timeout > 0
    assert server.events[2] == ("login", "correos.automaticos@slepllanquihue.cl", SMTP_PASSWORD)


@pytest.mark.asyncio
async def test_BE43_smtp_message_is_multipart_with_the_configured_sender(monkeypatch):
    server = FakeSMTPServer()
    await deliver(make_smtp(server, monkeypatch))
    msg = server.sent[0]
    assert msg["To"] == "ana.perez@slepllanquihue.cl"
    assert msg["From"] == "correos.automaticos@slepllanquihue.cl"
    assert msg["Subject"] == "Define tu contraseña"
    types = [p.get_content_type() for p in msg.walk() if not p.is_multipart()]
    assert types == ["text/plain", "text/html"]
    assert "definir-contrasena#token=abc" in msg.get_body(preferencelist=("plain",)).get_content()


@pytest.mark.asyncio
async def test_BE43_smtp_verifies_the_server_certificate(monkeypatch):
    server = FakeSMTPServer()
    await deliver(make_smtp(server, monkeypatch))
    context = server.events[1][1]
    assert isinstance(context, ssl.SSLContext)
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname is True


@pytest.mark.asyncio
async def test_BE43_smtp_port_465_uses_implicit_tls_without_starttls(monkeypatch):
    server = FakeSMTPServer()
    await deliver(make_smtp(server, monkeypatch, SMTP_PORT="465"))
    assert server.names() == ["SMTP_SSL", "login", "send", "quit"]
    kind, host, port, timeout, context = server.events[0]
    assert (host, port) == ("smtp.gmail.com", 465)
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname is True


@pytest.mark.asyncio
async def test_BE43_smtp_never_sends_in_plain_text_when_starttls_fails(monkeypatch):
    server = FakeSMTPServer(starttls_error=smtplib.SMTPNotSupportedError("STARTTLS extension not supported"))
    with pytest.raises(MailError) as exc:
        await deliver(make_smtp(server, monkeypatch))
    assert exc.value.code == "mail_send_failed"
    assert "login" not in server.names() and server.sent == []


@pytest.mark.asyncio
async def test_BE43_smtp_blocking_call_runs_outside_the_event_loop_thread(monkeypatch):
    server = FakeSMTPServer()
    await deliver(make_smtp(server, monkeypatch))
    assert server.login_thread is not None and server.login_thread != threading.get_ident()


@pytest.mark.asyncio
async def test_BE43_smtp_makes_no_gmail_api_request(monkeypatch):
    fake = FakeGoogle()
    server = FakeSMTPServer().install(monkeypatch)
    service = MailService(Settings(SMTP_ENV), transport=httpx.MockTransport(fake))
    await deliver(service)
    assert fake.calls == [] and server.sent


@pytest.mark.asyncio
async def test_BE43_smtp_rejected_login_is_auth_failed_and_logged_critical(monkeypatch, caplog):
    server = FakeSMTPServer(login_error=smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted"))
    with caplog.at_level(logging.CRITICAL, logger="mail"):
        with pytest.raises(MailError) as exc:
            await deliver(make_smtp(server, monkeypatch))
    assert exc.value.code == "mail_auth_failed"
    assert server.sent == []
    assert any(r.levelno == logging.CRITICAL for r in caplog.records)
    assert "SMTPAuthenticationError" in caplog.text


@pytest.mark.asyncio
async def test_BE43_smtp_timeout_has_a_stable_code(monkeypatch):
    server = FakeSMTPServer(connect_error=TimeoutError("timed out"))
    with pytest.raises(MailError) as exc:
        await deliver(make_smtp(server, monkeypatch))
    assert exc.value.code == "mail_timeout"


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [
    ConnectionRefusedError("refused"),
    smtplib.SMTPServerDisconnected("Connection unexpectedly closed"),
    smtplib.SMTPConnectError(421, b"service not available"),
    ssl.SSLCertVerificationError("certificate verify failed"),
])
async def test_BE43_smtp_connection_failures_map_to_send_failed(monkeypatch, error):
    server = FakeSMTPServer(connect_error=error)
    with pytest.raises(MailError) as exc:
        await deliver(make_smtp(server, monkeypatch))
    assert exc.value.code == "mail_send_failed"


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [
    smtplib.SMTPRecipientsRefused({"ana.perez@slepllanquihue.cl": (550, b"no such user")}),
    smtplib.SMTPSenderRefused(550, b"sender rejected", "correos.automaticos@slepllanquihue.cl"),
    smtplib.SMTPDataError(554, b"message rejected as spam"),
])
async def test_BE43_smtp_send_rejections_map_to_send_failed(monkeypatch, error):
    server = FakeSMTPServer(send_error=error)
    with pytest.raises(MailError) as exc:
        await deliver(make_smtp(server, monkeypatch))
    assert exc.value.code == "mail_send_failed"


@pytest.mark.asyncio
@pytest.mark.parametrize("to,subject", [
    ("a@slepllanquihue.cl\r\nBcc: victima@x.cl", "Hola"), ("a@slepllanquihue.cl", "Hola\nBcc: x@x.cl"),
])
async def test_BE43_smtp_header_injection_is_rejected_before_connecting(monkeypatch, to, subject):
    server = FakeSMTPServer()
    with pytest.raises(MailError) as exc:
        await make_smtp(server, monkeypatch).send(to, subject, "<p>x</p>", "x")
    assert exc.value.code == "invalid_message" and server.events == []


@pytest.mark.asyncio
async def test_BE43_smtp_no_secret_in_exception_or_log(monkeypatch, caplog):
    leaky = f"535 5.7.8 rejected for password {SMTP_PASSWORD}"
    failures = [
        {"login_error": smtplib.SMTPAuthenticationError(535, leaky.encode())},
        {"connect_error": smtplib.SMTPConnectError(421, leaky.encode())},
        {"send_error": smtplib.SMTPDataError(554, leaky.encode())},
        {"connect_error": TimeoutError(leaky)},
    ]
    for kwargs in failures:
        server = FakeSMTPServer(**kwargs)
        with caplog.at_level(logging.DEBUG):
            with pytest.raises(MailError) as exc:
                await deliver(make_smtp(server, monkeypatch))
        assert SMTP_PASSWORD not in str(exc.value) and SMTP_PASSWORD not in repr(exc.value)
    assert SMTP_PASSWORD not in caplog.text and "abcd" not in caplog.text
