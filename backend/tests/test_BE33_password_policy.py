"""
test_BE33_password_policy.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: US-26 · Política de contraseñas por entorno (R7, C17, T9)
NIST SP 800-63B-4 (26-ago-2025) §3.1.1.2: 15 caracteres como único factor, al menos 64 permitidos,
sin reglas de composición, sin rotación periódica, lista de bloqueo obligatoria.
"""
import inspect
import bcrypt
import pytest
from fastapi.testclient import TestClient
from app.auth.auth_service import auth_service
from app.config import settings

EMAIL = "juan.torres@slepllanquihue.cl"


def codes(password, email=EMAIL):
    return {v["code"] for v in auth_service.check_password_policy(password, email)}


def test_BE33_policy_defaults_follow_nist_800_63b_rev4():
    assert (settings.PASSWORD_MIN_LENGTH, settings.PASSWORD_MAX_LENGTH, settings.PASSWORD_REQUIRE_CHAR_CLASSES) == (15, 64, 0)


def test_BE33_policy_endpoint_public_and_minimal():
    from app.main import app
    r = TestClient(app).get("/api/auth/password-policy")                  # sin token
    assert r.status_code == 200
    assert r.json() == {"min_length": 15, "max_length": 64, "require_char_classes": 0}
    assert "common" not in r.text.lower() and "blocklist" not in r.text.lower()


def test_BE33_min_length_boundary():
    assert len("zorro-azul-nub") == 14 and len("zorro-azul-nube") == 15
    assert codes("zorro-azul-nub") == {"min_length"}
    assert codes("zorro-azul-nube") == set()


def test_BE33_max_length_and_bytes():
    ok64 = "frase-" + "z" * 58
    assert len(ok64) == 64 and codes(ok64) == set()                          # 64 exactos: permitidos (NIST: al menos 64)
    assert "max_length" in codes(ok64 + "x")
    assert "max_bytes" in codes("ñ" * 40)                                    # 40 caracteres = 80 bytes: 422, no el ValueError de bcrypt
    with pytest.raises(ValueError):
        auth_service.get_password_hash("ñ" * 40)                             # la capa de hash rechaza si alguien se salta la política


@pytest.mark.parametrize("password", [
    "password1234567", "contrasena12345", "Contraseña1234567", "administrador123",   # palabra común + número
    "123456789012345", "abcdefghijklmnopq", "qwertyuiopasdfgh", "aaaaaaaaaaaaaaa",  # secuencias y falta de variedad
    "slepllanquihue2026", "SLEP-Llanquihue-2026",                                     # contexto de la institución
])
def test_BE33_common_password_or_context_word_rejected(password):
    assert codes(password) & {"common_password", "context_word"}, password


def test_BE33_contextual_password_rejected():
    assert "context_word" in codes("mi-clave-juan.torres-2026")              # contiene el local-part del correo
    assert "context_word" in codes("bienvenido-a-llanquihue-1")
    assert "context_word" not in codes("zorro-azul-nube-de-tarde")


def test_BE33_a_good_passphrase_passes():
    for ok in ("zorro-azul-nube-de-tarde", "mi perro come pan los lunes", "Tr0pical-Bufanda-Lluvia"):
        assert codes(ok) == set(), ok


def test_BE33_char_classes_optional(monkeypatch):
    assert "char_classes" not in codes("solo-minusculas-y-guiones")          # NIST: sin reglas de composición por defecto
    monkeypatch.setattr(settings, "PASSWORD_REQUIRE_CHAR_CLASSES", 3)
    assert "char_classes" in codes("solo-minusculas-y-guiones")
    assert "char_classes" not in codes("Mayus-minus-1-largo-ok")
    monkeypatch.setattr(settings, "PASSWORD_REQUIRE_CHAR_CLASSES", 4)
    assert "char_classes" in codes("Mayus1minus1y1largo")
    assert "char_classes" not in codes("Mayus-minus-1-largo-ok!")


def test_BE33_password_is_nfkc_normalized():
    composed, decomposed = "frase-con-acentuación-ñandú", "frase-con-acentuación-ñandú"
    assert composed != decomposed
    hashed = auth_service.get_password_hash(decomposed)
    assert auth_service.verify_password(composed, hashed) and auth_service.verify_password(decomposed, hashed)


def test_BE33_legacy_hash_made_from_raw_text_still_verifies():
    raw = "contraseña-heredada-sin-normalizar"
    legacy = bcrypt.hashpw(raw.encode(), bcrypt.gensalt(rounds=4)).decode()
    assert auth_service.verify_password(raw, legacy)


def test_BE33_single_policy_function_no_second_implementation():
    """El cambio propio usa check_password_policy; el canje del enlace (F4) usará la misma."""
    from app.auth import auth_controller
    src = inspect.getsource(auth_controller)
    assert src.count("check_password_policy") == 1 and "len(payload.new_password)" not in src
    assert not hasattr(auth_service, "validate_password")


def test_BE33_policy_numbers_come_from_settings_only():
    src = inspect.getsource(auth_service.check_password_policy)
    assert "settings.PASSWORD_MIN_LENGTH" in src and "settings.PASSWORD_MAX_LENGTH" in src
    assert "< 15" not in src and "> 64" not in src
