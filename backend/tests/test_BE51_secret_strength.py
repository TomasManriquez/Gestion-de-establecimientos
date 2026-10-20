"""
test_BE51_secret_strength.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: SEC-1 · Secretos con longitud mínima y sin valores públicos

Verifica que:
  - JWT_SECRET de menos de 32 caracteres impide arrancar
  - el valor legado del repositorio y el marcador de la plantilla de producción se rechazan
    (en JWT_SECRET y en ADMIN_PASSWORD)
  - un secreto de 32 caracteres o más, propio, se acepta
  - el compose de desarrollo ya no trae secretos literales: los lee del .env de la raíz
"""
from pathlib import Path
import pytest
from app.config import ConfigError, Settings
from tests.test_BE14_settings_fail_fast import VALID_ENV

ROOT = Path(__file__).resolve().parents[2]
LEGACY_JWT = "super-secret-slep-key-2026-llanquihue-digital-management"
LEGACY_ADMIN = "dev-only-admin-password-change-me"


def test_BE51_short_jwt_secret_rejected():
    for n in (1, 12, 31):
        with pytest.raises(ConfigError, match="JWT_SECRET"):
            Settings({**VALID_ENV, "JWT_SECRET": "a" * n})


def test_BE51_32_chars_accepted():
    assert Settings({**VALID_ENV, "JWT_SECRET": "a" * 32}).JWT_SECRET == "a" * 32


@pytest.mark.parametrize("value", [LEGACY_JWT, LEGACY_JWT.upper(), "CAMBIA_ESTO_por_secret_de_128_chars_hexadecimales"])
def test_BE51_known_or_placeholder_jwt_secret_rejected(value):
    with pytest.raises(ConfigError, match="JWT_SECRET"):
        Settings({**VALID_ENV, "JWT_SECRET": value})


@pytest.mark.parametrize("value", [LEGACY_ADMIN, "CAMBIA_ESTO_por_password_admin_seguro"])
def test_BE51_known_or_placeholder_admin_password_rejected(value):
    with pytest.raises(ConfigError, match="ADMIN_PASSWORD"):
        Settings({**VALID_ENV, "ADMIN_PASSWORD": value})


def test_BE51_error_message_does_not_echo_the_secret():
    with pytest.raises(ConfigError) as exc:
        Settings({**VALID_ENV, "JWT_SECRET": "corto-y-secreto"})
    assert "corto-y-secreto" not in str(exc.value)


def test_BE51_dev_compose_has_no_literal_secrets():
    dev = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    for line in dev.splitlines():
        if "JWT_SECRET=" in line or "ADMIN_PASSWORD=" in line:
            assert "${" in line, f"secreto literal en docker-compose.yml: {line.split('=')[0].strip()}"
    assert LEGACY_JWT not in dev and LEGACY_ADMIN not in dev
