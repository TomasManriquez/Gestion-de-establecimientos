"""
test_BE42_mail_settings.py
━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: US-14 · Configuración del correo (ADR-012 §7)

Verifica que:
  - MAIL_MODE y PUBLIC_BASE_URL son obligatorias y sin default
  - MAIL_MODE solo admite gmail o console
  - `console` se rechaza si PUBLIC_BASE_URL no es localhost/127.0.0.1 (no puede quedar activo en producción)
  - `gmail` exige remitente, refresh token y credenciales del cliente OAuth, y https fuera de localhost
  - PUBLIC_BASE_URL se normaliza (sin barra final) y rechaza rutas, credenciales y esquemas raros
  - ningún secreto de correo aparece en repr(Settings)
"""
import pytest
from app.config import Settings, ConfigError

BASE = {
    "JWT_SECRET": "x" * 64, "ADMIN_PASSWORD": "una-clave-de-prueba",
    "ALLOWED_EMAIL_DOMAINS": "slepllanquihue.cl", "BOOTSTRAP_ADMIN_EMAIL": "admin@slepllanquihue.cl",
    "GOOGLE_AUTO_PROVISION": "false",
}
GMAIL = {
    **BASE, "MAIL_MODE": "gmail", "PUBLIC_BASE_URL": "https://gestion.slepllanquihue.cl",
    "GMAIL_SENDER_ADDRESS": "no-responder@slepllanquihue.cl", "GMAIL_REFRESH_TOKEN": "1//refresh-token-secreto",
    "GOOGLE_CLIENT_ID": "id.apps.googleusercontent.com", "GOOGLE_CLIENT_SECRET": "GOCSPX-secreto-del-cliente",
}
CONSOLE = {**BASE, "MAIL_MODE": "console", "PUBLIC_BASE_URL": "http://localhost:5173"}


@pytest.mark.parametrize("missing", ["MAIL_MODE", "PUBLIC_BASE_URL"])
def test_BE42_missing_mail_env_fails_fast(missing):
    with pytest.raises(ConfigError, match=missing):
        Settings({k: v for k, v in CONSOLE.items() if k != missing})


def test_BE42_invalid_mail_mode():
    with pytest.raises(ConfigError, match="MAIL_MODE"):
        Settings({**CONSOLE, "MAIL_MODE": "smtp"})


def test_BE42_mode_is_case_insensitive():
    assert Settings({**CONSOLE, "MAIL_MODE": " Console "}).MAIL_MODE == "console"


@pytest.mark.parametrize("url", ["http://localhost:5173", "http://127.0.0.1:8000", "https://localhost"])
def test_BE42_console_allowed_on_local_hosts(url):
    assert Settings({**CONSOLE, "PUBLIC_BASE_URL": url}).MAIL_MODE == "console"


@pytest.mark.parametrize("url", [
    "https://gestion.slepllanquihue.cl", "http://192.168.1.10:5173", "http://localhost.evil.com",
])
def test_BE42_console_rejected_outside_localhost(url):
    with pytest.raises(ConfigError, match="console"):
        Settings({**CONSOLE, "PUBLIC_BASE_URL": url})


def test_BE42_valid_gmail_config():
    s = Settings(GMAIL)
    assert s.MAIL_MODE == "gmail"
    assert s.GMAIL_SENDER_ADDRESS == "no-responder@slepllanquihue.cl"


@pytest.mark.parametrize("name", ["GMAIL_SENDER_ADDRESS", "GMAIL_REFRESH_TOKEN", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"])
def test_BE42_gmail_requires_credentials(name):
    with pytest.raises(ConfigError, match=name):
        Settings({k: v for k, v in GMAIL.items() if k != name})
    with pytest.raises(ConfigError, match=name):
        Settings({**GMAIL, name: "   "})


def test_BE42_gmail_sender_must_look_like_an_address():
    with pytest.raises(ConfigError, match="GMAIL_SENDER_ADDRESS"):
        Settings({**GMAIL, "GMAIL_SENDER_ADDRESS": "no-es-un-correo"})


def test_BE42_gmail_requires_https_outside_localhost():
    with pytest.raises(ConfigError, match="https"):
        Settings({**GMAIL, "PUBLIC_BASE_URL": "http://gestion.slepllanquihue.cl"})
    assert Settings({**GMAIL, "PUBLIC_BASE_URL": "http://localhost:5173"}).PUBLIC_BASE_URL == "http://localhost:5173"


def test_BE42_credentials_not_required_in_console_mode():
    s = Settings(CONSOLE)
    assert s.GMAIL_REFRESH_TOKEN == "" and s.GOOGLE_CLIENT_SECRET == ""


@pytest.mark.parametrize("raw,expected", [
    ("https://gestion.slepllanquihue.cl/", "https://gestion.slepllanquihue.cl"),
    ("  https://gestion.slepllanquihue.cl  ", "https://gestion.slepllanquihue.cl"),
    ("https://gestion.slepllanquihue.cl:8443", "https://gestion.slepllanquihue.cl:8443"),
])
def test_BE42_public_base_url_is_normalized(raw, expected):
    assert Settings({**GMAIL, "PUBLIC_BASE_URL": raw}).PUBLIC_BASE_URL == expected


@pytest.mark.parametrize("raw", [
    "gestion.slepllanquihue.cl", "ftp://gestion.slepllanquihue.cl", "https://", "https://u:p@gestion.slepllanquihue.cl",
    "https://gestion.slepllanquihue.cl/app", "https://gestion.slepllanquihue.cl?x=1", "https://gestion.slepllanquihue.cl#a",
    "javascript:alert(1)",
])
def test_BE42_public_base_url_rejects_bad_values(raw):
    with pytest.raises(ConfigError, match="PUBLIC_BASE_URL"):
        Settings({**GMAIL, "PUBLIC_BASE_URL": raw})


def test_BE42_repr_hides_mail_secrets():
    text = repr(Settings(GMAIL))
    for secret in ("1//refresh-token-secreto", "GOCSPX-secreto-del-cliente"):
        assert secret not in text
