"""
test_BE14_settings_fail_fast.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: US-07 · Configuración sin defaults peligrosos (T9, cierra D2)

Verifica que:
  - Sin una variable de identidad o de secreto la app no arranca, y el mensaje la nombra
  - La política de contraseñas fuera de rango impide el arranque
  - ALLOWED_EMAIL_DOMAINS se normaliza (minúsculas, sin '@', sin duplicados)
  - Toda variable que lee Settings está declarada en la plantilla y en los dos compose
  - JWT_SECRET y ADMIN_PASSWORD ya no tienen default

PUBLIC_BASE_URL y MAIL_MODE se validan en F4, cuando se implementa el envío de correo.
"""
from pathlib import Path
import pytest
from app.config import Settings, ConfigError

ROOT = Path(__file__).resolve().parents[2]

VALID_ENV = {
    "JWT_SECRET": "x" * 64,
    "ADMIN_PASSWORD": "una-clave-de-prueba",
    "ALLOWED_EMAIL_DOMAINS": "slepllanquihue.cl",
    "BOOTSTRAP_ADMIN_EMAIL": "admin@slepllanquihue.cl",
}


def test_BE14_valid_env_builds_settings_with_nist_defaults():
    s = Settings(VALID_ENV)
    assert s.PASSWORD_MIN_LENGTH == 15
    assert s.PASSWORD_MAX_LENGTH == 64
    assert s.PASSWORD_REQUIRE_CHAR_CLASSES == 0
    assert s.ACCESS_TOKEN_EXPIRE_MINUTES == 180


@pytest.mark.parametrize("missing", ["JWT_SECRET", "ADMIN_PASSWORD", "ALLOWED_EMAIL_DOMAINS", "BOOTSTRAP_ADMIN_EMAIL"])
def test_BE14_missing_required_env_fails_fast(missing):
    env = {k: v for k, v in VALID_ENV.items() if k != missing}
    with pytest.raises(ConfigError, match=missing):
        Settings(env)


@pytest.mark.parametrize("blank", ["", "   "])
def test_BE14_blank_required_env_counts_as_missing(blank):
    with pytest.raises(ConfigError, match="JWT_SECRET"):
        Settings({**VALID_ENV, "JWT_SECRET": blank})


@pytest.mark.parametrize("name,value", [
    ("PASSWORD_MIN_LENGTH", "7"),
    ("PASSWORD_MAX_LENGTH", "63"),
    ("PASSWORD_REQUIRE_CHAR_CLASSES", "5"),
    ("PASSWORD_REQUIRE_CHAR_CLASSES", "-1"),
    ("PASSWORD_MIN_LENGTH", "abc"),
])
def test_BE14_password_policy_out_of_range_fails(name, value):
    with pytest.raises(ConfigError, match=name):
        Settings({**VALID_ENV, name: value})


def test_BE14_min_length_cannot_exceed_max_length():
    with pytest.raises(ConfigError, match="PASSWORD_MIN_LENGTH"):
        Settings({**VALID_ENV, "PASSWORD_MIN_LENGTH": "80", "PASSWORD_MAX_LENGTH": "64"})


def test_BE14_allowed_domains_parsing():
    s = Settings({**VALID_ENV, "ALLOWED_EMAIL_DOMAINS": "@SLEPllanquihue.cl, slepllanquihue.cl ,Otro.Org"})
    assert s.ALLOWED_EMAIL_DOMAINS == ["slepllanquihue.cl", "otro.org"]


@pytest.mark.parametrize("raw", [",,", "sin-punto", "con espacio.cl", "a@b.cl"])
def test_BE14_allowed_domains_invalid_or_empty_fails(raw):
    with pytest.raises(ConfigError, match="ALLOWED_EMAIL_DOMAINS"):
        Settings({**VALID_ENV, "ALLOWED_EMAIL_DOMAINS": raw})


def test_BE14_bootstrap_email_must_belong_to_allowed_domains():
    with pytest.raises(ConfigError, match="BOOTSTRAP_ADMIN_EMAIL"):
        Settings({**VALID_ENV, "BOOTSTRAP_ADMIN_EMAIL": "admin@gmail.com"})


def test_BE14_bootstrap_email_is_normalized():
    s = Settings({**VALID_ENV, "BOOTSTRAP_ADMIN_EMAIL": "  Admin@SLEPllanquihue.CL "})
    assert s.BOOTSTRAP_ADMIN_EMAIL == "admin@slepllanquihue.cl"


def test_BE14_jwt_secret_and_admin_password_have_no_default():
    """D2: antes tenían un default funcional público en el repositorio."""
    for name in ("JWT_SECRET", "ADMIN_PASSWORD"):
        with pytest.raises(ConfigError, match=name):
            Settings({k: v for k, v in VALID_ENV.items() if k != name})
    src = (ROOT / "backend/app/config.py").read_text(encoding="utf-8")
    assert "super-secret-slep-key" not in src
    assert "admin123" not in src


def test_BE14_repr_hides_secrets():
    assert "x" * 10 not in repr(Settings(VALID_ENV))
    assert "una-clave-de-prueba" not in repr(Settings(VALID_ENV))


def test_BE14_every_env_var_declared_in_templates_and_compose():
    """Regla 3 de CLAUDE.md: variable nueva => config.py + los dos compose + la plantilla."""
    template = (ROOT / ".env.production.template").read_text(encoding="utf-8")
    dev = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    prod = (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
    # MONGODB_URL se compone en producción a partir de MONGO_ROOT_* y no va en la plantilla.
    for var in Settings.ENV_VARS:
        assert var in dev, f"{var} no está en docker-compose.yml"
        assert var in prod, f"{var} no está en docker-compose.prod.yml"
        if var != "MONGODB_URL":
            assert var in template, f"{var} no está en .env.production.template"
