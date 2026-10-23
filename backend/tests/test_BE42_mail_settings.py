"""
test_BE42_mail_settings.py
━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: US-14 · Configuración del correo (ADR-012 §7)

Verifica que:
  - MAIL_MODE y PUBLIC_BASE_URL son obligatorias y sin default
  - MAIL_MODE solo admite smtp, gmail o console
  - `console` se rechaza si PUBLIC_BASE_URL no es localhost/127.0.0.1 (no puede quedar activo en producción)
  - `gmail` exige remitente, refresh token y credenciales del cliente OAuth, y https fuera de localhost
  - `smtp` (ADR-017) exige host, puerto, usuario, contraseña y remitente; puerto solo 587 o 465; https fuera de
    localhost; no exige ninguna variable de Gmail; rechaza una contraseña de ejemplo
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
SMTP = {
    **BASE, "MAIL_MODE": "smtp", "PUBLIC_BASE_URL": "https://gestion.slepllanquihue.cl",
    "SMTP_HOST": "smtp.gmail.com", "SMTP_PORT": "587", "SMTP_USERNAME": "correos.automaticos@slepllanquihue.cl",
    "SMTP_PASSWORD": "abcd efgh ijkl mnop", "SMTP_SENDER_ADDRESS": "correos.automaticos@slepllanquihue.cl",
}
CONSOLE = {**BASE, "MAIL_MODE": "console", "PUBLIC_BASE_URL": "http://localhost:5173"}


@pytest.mark.parametrize("missing", ["MAIL_MODE", "PUBLIC_BASE_URL"])
def test_BE42_missing_mail_env_fails_fast(missing):
    with pytest.raises(ConfigError, match=missing):
        Settings({k: v for k, v in CONSOLE.items() if k != missing})


def test_BE42_invalid_mail_mode():
    with pytest.raises(ConfigError, match="MAIL_MODE"):
        Settings({**CONSOLE, "MAIL_MODE": "sendgrid"})


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
    assert s.GMAIL_REFRESH_TOKEN == "" and s.GOOGLE_CLIENT_SECRET == "" and s.SMTP_PASSWORD == ""


def test_BE42_valid_smtp_config():
    s = Settings(SMTP)
    assert s.MAIL_MODE == "smtp"
    assert (s.SMTP_HOST, s.SMTP_PORT) == ("smtp.gmail.com", 587)
    assert s.SMTP_SENDER_ADDRESS == "correos.automaticos@slepllanquihue.cl"
    assert s.SMTP_PASSWORD == "abcd efgh ijkl mnop"          # los espacios de la contraseña de aplicación se respetan


def test_BE42_smtp_does_not_need_any_gmail_variable():
    s = Settings(SMTP)
    assert s.GMAIL_REFRESH_TOKEN == "" and s.GOOGLE_CLIENT_SECRET == "" and s.GMAIL_SENDER_ADDRESS == ""


@pytest.mark.parametrize("name", ["SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_SENDER_ADDRESS"])
def test_BE42_smtp_requires_every_variable(name):
    with pytest.raises(ConfigError, match=name):
        Settings({k: v for k, v in SMTP.items() if k != name})
    with pytest.raises(ConfigError, match=name):
        Settings({**SMTP, name: "   "})


@pytest.mark.parametrize("port", ["25", "2525", "0", "-1", "80"])
def test_BE42_smtp_port_must_be_a_tls_port(port):
    with pytest.raises(ConfigError, match="SMTP_PORT"):
        Settings({**SMTP, "SMTP_PORT": port})


def test_BE42_smtp_port_must_be_an_integer():
    with pytest.raises(ConfigError, match="SMTP_PORT"):
        Settings({**SMTP, "SMTP_PORT": "quinientos"})


@pytest.mark.parametrize("port", ["587", "465"])
def test_BE42_smtp_accepts_starttls_and_implicit_tls_ports(port):
    assert Settings({**SMTP, "SMTP_PORT": port}).SMTP_PORT == int(port)


@pytest.mark.parametrize("host", ["smtp://smtp.gmail.com", "smtp.gmail.com/ruta", "smtp gmail.com", "user@smtp.gmail.com", "-smtp.com"])
def test_BE42_smtp_host_must_be_a_bare_hostname(host):
    with pytest.raises(ConfigError, match="SMTP_HOST"):
        Settings({**SMTP, "SMTP_HOST": host})


def test_BE42_smtp_sender_must_look_like_an_address():
    with pytest.raises(ConfigError, match="SMTP_SENDER_ADDRESS"):
        Settings({**SMTP, "SMTP_SENDER_ADDRESS": "no-es-un-correo"})


def test_BE42_smtp_rejects_a_placeholder_password():
    with pytest.raises(ConfigError, match="SMTP_PASSWORD"):
        Settings({**SMTP, "SMTP_PASSWORD": "CAMBIA_ESTO_por_la_contrasena_de_aplicacion"})


def test_BE42_smtp_requires_https_outside_localhost():
    with pytest.raises(ConfigError, match="https"):
        Settings({**SMTP, "PUBLIC_BASE_URL": "http://gestion.slepllanquihue.cl"})
    assert Settings({**SMTP, "PUBLIC_BASE_URL": "http://localhost:5173"}).MAIL_MODE == "smtp"


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
    assert "abcd efgh ijkl mnop" not in repr(Settings(SMTP))
