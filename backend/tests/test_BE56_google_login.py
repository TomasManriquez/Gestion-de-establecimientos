"""
test_BE56_google_login.py
━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: T11 / S2 · Login con Google y alta automática (C24, G1, G2, ADR-015)

Los id_token se firman de verdad (RS256, clave de prueba) y solo se sustituye la descarga de los
certificados de Google: la verificación de firma, `aud` y `exp` es la de `google-auth`.

Verifica que:
  - un token de otro dominio, sin `hd`, con `hd` distinto del correo, `email_verified=false`, de otra
    `aud`, vencido, con `iss` ajeno, con `iat` antiguo, sin `sub` o con otra firma da el mismo 401 y
    NO crea ningún documento
  - la cuenta nueva es `viewer` en `datos`, sin `iam`, sin asignar; ninguna claim cambia el rol
  - dos logins del mismo correo nuevo crean una sola cuenta (aun perdiendo la carrera)
  - un usuario `disabled` no entra y Google no lo reactiva
  - un usuario existente entra por correo y no cambia su rol ni su pertenencia
  - `invited` pasa a `active`; una cuenta vinculada a otro `subject` no entra
  - con GOOGLE_AUTO_PROVISION=false un correo sin cuenta recibe el mismo 401 y no se crea nada
  - ni la respuesta ni los logs contienen el `credential`
  - exceder el límite por IP da 429 con Retry-After; los logins correctos no cuentan
  - GET /api/auth/config expone solo el client id
"""
import copy
import logging
import time
from unittest.mock import patch

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.config import settings
from tests.conftest import ADMIN_USER, EDITOR_USER, _user, prepare_org

CLIENT_ID = "test-client-id.apps.googleusercontent.com"
NEW_EMAIL = "persona.nueva@slepllanquihue.cl"


def _keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    return private, public.decode()


PRIVATE, PUBLIC = _keypair()
OTHER_PRIVATE, _ = _keypair()


def make_token(private=None, **overrides):
    now = int(time.time())
    claims = {"iss": "https://accounts.google.com", "aud": CLIENT_ID, "sub": "110000000000000000001",
              "email": NEW_EMAIL, "email_verified": True, "hd": "slepllanquihue.cl",
              "given_name": "Persona", "family_name": "Nueva", "iat": now, "exp": now + 3600}
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, private or PRIVATE, algorithm="RS256", headers={"kid": "k1"})


@pytest.fixture(autouse=True)
def google_env(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(settings, "GOOGLE_AUTO_PROVISION", True)
    with patch("google.oauth2.id_token._fetch_certs", return_value={"k1": PUBLIC}):
        yield


@pytest.fixture
def ctx(fake_db):
    prepare_org(fake_db, ADMIN_USER, EDITOR_USER)
    from app.main import app
    return TestClient(app), fake_db


def login(c, credential=None, **overrides):
    return c.post("/api/auth/google", json={"credential": credential or make_token(**overrides)})


def snapshot(db):
    return {name: copy.deepcopy(col.docs) for name, col in db._cols.items() if name != "rate_limits"}


def user_by_email(db, email):
    return next((d for d in db.users.docs if d.get("email") == email), None)


def me(c, token):
    return c.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})


# ─── rechazos: mismo 401 y nada se escribe ───────────────────────────────────

NOW = lambda: int(time.time())
REJECTED = {
    "otro dominio con hd propio": dict(email="x@otro.cl", hd="otro.cl"),
    "cuenta personal sin hd": dict(email="x@gmail.com", hd=None),
    "hd permitido pero correo de otro dominio": dict(email="x@otro.cl"),
    "correo del dominio con hd ajeno": dict(hd="otro.cl"),
    "correo sin verificar": dict(email_verified=False),
    "correo verificado como texto": dict(email_verified="true"),
    "otra audiencia": dict(aud="otro-cliente.apps.googleusercontent.com"),
    "vencido": dict(iat=NOW() - 7200, exp=NOW() - 3600),
    "emisor ajeno": dict(iss="https://evil.example"),
    "iat antiguo (más de 5 minutos)": dict(iat=NOW() - 600),
    "iat en el futuro": dict(iat=NOW() + 600),
    "sin sub": dict(sub=None),
    "sin correo": dict(email=None),
}


@pytest.mark.parametrize("case", list(REJECTED))
def test_BE56_rejected_tokens_give_the_same_401_and_write_nothing(ctx, case):
    c, db = ctx
    before = snapshot(db)
    r = login(c, **REJECTED[case])
    assert r.status_code == 401, case
    assert r.json() == {"detail": "Could not validate credentials"}
    assert r.headers["www-authenticate"] == "Bearer"
    assert snapshot(db) == before, "un rechazo no debe crear ni modificar documentos"


def test_BE56_wrong_signature_and_garbage_rejected(ctx):
    c, db = ctx
    before = snapshot(db)
    assert login(c, credential=make_token(private=OTHER_PRIVATE)).status_code == 401
    assert login(c, credential="no.es.un.jwt").status_code == 401
    assert login(c, credential="x" * 9000).status_code == 401
    assert jwt.encode({"sub": "1"}, "k" * 40, algorithm="HS256")
    assert login(c, credential=jwt.encode({"sub": "1", "aud": CLIENT_ID}, "k" * 40, algorithm="HS256")).status_code == 401
    assert snapshot(db) == before


def test_BE56_missing_client_id_rejects_everything(ctx, monkeypatch):
    c, db = ctx
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")
    assert login(c).status_code == 401
    assert user_by_email(db, NEW_EMAIL) is None


# ─── alta automática ─────────────────────────────────────────────────────────

def test_BE56_new_account_is_unassigned_active_viewer_in_datos(ctx):
    c, db = ctx
    r = login(c)
    assert r.status_code == 200 and r.json()["token_type"] == "bearer"
    doc = user_by_email(db, NEW_EMAIL)
    assert doc["status"] == "active"
    assert [(a["platform_id"], a["role"]) for a in doc["access"]] == [("datos", "viewer")]
    assert doc["is_slep_staff"] is None and doc["unit_id"] is None and doc["rbd"] is None and doc["positions"] == []
    assert (doc["first_name"], doc["last_name"]) == ("Persona", "Nueva")
    assert [(p["provider"], p["subject"]) for p in doc["auth_providers"]] == [("google", "110000000000000000001")]
    body = me(c, r.json()["access_token"]).json()
    assert body["role"] == "viewer" and body["email"] == NEW_EMAIL
    assert not any(a["platform_id"] == "iam" for a in body["access"])
    assert doc["last_login_at"] is not None


def test_BE56_autoprovision_is_audited(ctx):
    c, db = ctx
    login(c)
    entries = [e for e in db.audit_log.docs if e["action"] == "user.autoprovision"]
    assert len(entries) == 1 and entries[0]["target_id"] == str(user_by_email(db, NEW_EMAIL)["_id"])
    assert not [e for e in db.audit_log.docs if e["action"] == "user.create"]


def test_BE56_no_token_claim_can_change_the_role(ctx):
    c, db = ctx
    login(c, role="admin", roles=["admin"], access=[{"platform_id": "iam", "role": "admin"}], is_slep_staff=True,
          unit_id="6600000000000000000000f1", status="active", hashed_password="x")
    doc = user_by_email(db, NEW_EMAIL)
    assert [(a["platform_id"], a["role"]) for a in doc["access"]] == [("datos", "viewer")]
    assert doc["is_slep_staff"] is None and doc["unit_id"] is None


def test_BE56_missing_names_fall_back_without_failing(ctx):
    c, db = ctx
    assert login(c, given_name=None, family_name=None).status_code == 200
    doc = user_by_email(db, NEW_EMAIL)
    assert doc["first_name"] == "persona.nueva" and doc["last_name"]


def test_BE56_second_login_reuses_the_same_account(ctx):
    c, db = ctx
    assert login(c).status_code == 200 and login(c).status_code == 200
    assert len([d for d in db.users.docs if d["email"] == NEW_EMAIL]) == 1


def test_BE56_two_simultaneous_logins_of_a_new_email_create_one_account(ctx):
    """El segundo login no ve la cuenta (la carrera): el índice único de `email` la frena y el
    flujo recupera la cuenta que creó el primero."""
    c, db = ctx
    assert login(c).status_code == 200
    from app.users.users_service import users_service
    real_subject, real_login = users_service.find_by_google_subject, users_service.find_by_login
    calls = {"n": 0}

    async def blind_subject(subject):
        return None

    async def blind_once(login_name):
        calls["n"] += 1
        return None if calls["n"] == 1 else await real_login(login_name)

    with patch.object(users_service, "find_by_google_subject", blind_subject), \
            patch.object(users_service, "find_by_login", blind_once):
        r = login(c)
    assert r.status_code == 200
    assert len([d for d in db.users.docs if d["email"] == NEW_EMAIL]) == 1


def test_BE56_autoprovision_off_gives_the_same_401_and_creates_nothing(ctx, monkeypatch):
    c, db = ctx
    monkeypatch.setattr(settings, "GOOGLE_AUTO_PROVISION", False)
    before = snapshot(db)
    r = login(c)
    assert r.status_code == 401 and r.json() == {"detail": "Could not validate credentials"}
    assert snapshot(db) == before


def test_BE56_autoprovision_off_still_lets_existing_accounts_in(ctx, monkeypatch):
    c, db = ctx
    monkeypatch.setattr(settings, "GOOGLE_AUTO_PROVISION", False)
    assert login(c, email=EDITOR_USER["email"], sub="220").status_code == 200


# ─── cuentas existentes ──────────────────────────────────────────────────────

def test_BE56_existing_user_enters_by_email_and_keeps_role_and_membership(ctx):
    c, db = ctx
    before = copy.deepcopy(user_by_email(db, ADMIN_USER["email"]))
    r = login(c, email=ADMIN_USER["email"], sub="330", given_name="Otro", family_name="Nombre")
    assert r.status_code == 200
    after = user_by_email(db, ADMIN_USER["email"])
    for field in ("access", "is_slep_staff", "unit_id", "rbd", "positions", "status", "first_name", "last_name"):
        assert after[field] == before[field], field
    assert [p["provider"] for p in after["auth_providers"]] == ["local", "google"]
    assert me(c, r.json()["access_token"]).json()["role"] == "admin"


def test_BE56_invited_account_becomes_active_and_linked(ctx):
    c, db = ctx
    invited = _user("6600000000000000000000b7", "invitada@slepllanquihue.cl", "In", "Vitada", [("datos", "editor")],
                    status="invited", auth_providers=[])
    from tests.conftest import seed_users
    seed_users(db, invited)
    assert login(c, email=invited["email"], sub="440").status_code == 200
    doc = user_by_email(db, invited["email"])
    assert doc["status"] == "active" and doc["auth_providers"][0]["subject"] == "440"
    assert [(a["platform_id"], a["role"]) for a in doc["access"]] == [("datos", "editor")]


def test_BE56_disabled_user_cannot_enter_and_is_not_reactivated(ctx):
    c, db = ctx
    disabled = _user("6600000000000000000000b8", "baja@slepllanquihue.cl", "Ba", "Ja", [("datos", "viewer")],
                     status="disabled", auth_providers=[])
    from tests.conftest import seed_users
    seed_users(db, disabled)
    before = snapshot(db)
    assert login(c, email=disabled["email"], sub="550").status_code == 401
    assert snapshot(db) == before and user_by_email(db, disabled["email"])["status"] == "disabled"


def test_BE56_disabled_user_already_linked_cannot_enter(ctx):
    c, db = ctx
    linked = _user("6600000000000000000000b9", "vinculada@slepllanquihue.cl", "Vi", "Nculada", [("datos", "viewer")],
                   status="disabled", auth_providers=[{"provider": "google", "subject": "660", "linked_at": None}])
    from tests.conftest import seed_users
    seed_users(db, linked)
    assert login(c, email=linked["email"], sub="660").status_code == 401
    assert user_by_email(db, linked["email"])["status"] == "disabled"


def test_BE56_account_linked_to_another_subject_cannot_enter(ctx):
    c, db = ctx
    linked = _user("6600000000000000000000ba", "dueno@slepllanquihue.cl", "Du", "Eno", [("datos", "viewer")],
                   auth_providers=[{"provider": "google", "subject": "770", "linked_at": None}])
    from tests.conftest import seed_users
    seed_users(db, linked)
    before = snapshot(db)
    assert login(c, email=linked["email"], sub="999").status_code == 401
    assert snapshot(db) == before


# ─── secretos y límite ───────────────────────────────────────────────────────

def test_BE56_credential_never_appears_in_responses_or_logs(ctx, caplog):
    c, db = ctx
    caplog.set_level(logging.DEBUG)
    good, bad = make_token(), make_token(email_verified=False)
    responses = [login(c, credential=good), login(c, credential=bad), login(c, credential="basura-" + good[:40])]
    for secret in (good, bad, good.split(".")[1], good.split(".")[2]):
        assert secret not in caplog.text
        assert all(secret not in r.text for r in responses)


def test_BE56_rejections_over_the_ip_limit_give_429_with_retry_after(ctx):
    c, db = ctx
    from app.auth.auth_entity import GOOGLE_IP_LIMIT
    bad = make_token(email_verified=False)
    assert [login(c, credential=bad).status_code for _ in range(GOOGLE_IP_LIMIT)] == [401] * GOOGLE_IP_LIMIT
    blocked = login(c)                                       # aun con un token bueno
    assert blocked.status_code == 429 and int(blocked.headers["Retry-After"]) > 0


def test_BE56_successful_logins_do_not_count_toward_the_limit(ctx):
    c, db = ctx
    from app.auth.auth_entity import GOOGLE_IP_LIMIT
    for _ in range(GOOGLE_IP_LIMIT + 5):
        assert login(c).status_code == 200


def test_BE56_rate_limit_key_does_not_store_the_ip_in_clear(ctx):
    c, db = ctx
    login(c, email_verified=False)
    keys = [d["key"] for d in db.rate_limits.docs]
    assert keys and all(k.startswith("google-ip:") and "testclient" not in k for k in keys)


# ─── configuración pública ───────────────────────────────────────────────────

def test_BE56_config_exposes_only_the_client_id(ctx, monkeypatch):
    c, db = ctx
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "GOCSPX-no-debe-salir")
    r = c.get("/api/auth/config")
    assert r.status_code == 200 and r.json() == {"google_client_id": CLIENT_ID}
    assert "GOCSPX" not in r.text


def test_BE56_unknown_body_fields_are_rejected(ctx):
    c, db = ctx
    assert c.post("/api/auth/google", json={"credential": make_token(), "role": "admin"}).status_code == 422
    assert c.post("/api/auth/google", json={}).status_code == 422
