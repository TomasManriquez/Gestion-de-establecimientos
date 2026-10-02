"""
test_BE11_session_sub_and_revocation.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: US-04 · Sesión con `sub` estable y revocable (C6, C16, T3)

Verifica que:
  - el token lleva sub = str(_id) e iat
  - los tokens legados con sub = username siguen sirviendo mientras dure la compatibilidad
  - desactivar a un usuario o cambiar su contraseña corta las sesiones anteriores
  - todo fallo de autenticación es el mismo 401, sin distinguir el motivo
  - el login acepta el correo (normalizado) y el username legado; invited/disabled no entran
"""
import time
from datetime import datetime, timedelta, timezone
import jwt
import pytest
from fastapi.testclient import TestClient
from app.config import settings
from tests.conftest import ADMIN_USER, EDITOR_USER, seed_users, user_with_password, bearer_for

PASSWORD = "una-clave-larga-de-prueba"


def client():
    from app.main import app
    return TestClient(app)


def me(c, headers=None):
    return c.get("/api/auth/me", headers=headers or {})


def raw_token(payload, secret=None, exp_delta=timedelta(minutes=5)):
    body = {"exp": datetime.now(timezone.utc) + exp_delta, **payload}
    return {"Authorization": "Bearer " + jwt.encode(body, secret or settings.JWT_SECRET, algorithm="HS256")}


def test_BE11_token_sub_is_object_id_string(fake_db):
    docs = seed_users(fake_db, user_with_password(ADMIN_USER, PASSWORD))
    c = client()
    r = c.post("/api/auth/login", json={"username": "admin@slepllanquihue.cl", "password": PASSWORD})
    payload = jwt.decode(r.json()["access_token"], settings.JWT_SECRET, algorithms=["HS256"])
    assert payload["sub"] == str(docs[0]["_id"])
    assert "@" not in payload["sub"] and "iat" in payload and isinstance(payload["iat"], int)


def test_BE11_legacy_username_sub_still_accepted(fake_db):
    seed_users(fake_db, {**ADMIN_USER, "username": "admin"})
    assert me(client(), raw_token({"sub": "admin"})).status_code == 200


@pytest.mark.parametrize("status", ["disabled", "invited"])
def test_BE11_disabled_user_token_rejected(fake_db, status):
    seed_users(fake_db, {**ADMIN_USER, "status": "active"})
    c = client()
    headers = bearer_for(ADMIN_USER)
    assert me(c, headers).status_code == 200
    fake_db.users.docs[0]["status"] = status                       # desactivado con el token aún vigente
    assert me(c, headers).status_code == 401


def test_BE11_token_issued_before_password_change_rejected(fake_db):
    changed = (datetime.now(timezone.utc) - timedelta(seconds=30)).replace(tzinfo=None)   # cambió hace 30 s
    user = {**ADMIN_USER, "auth_providers": [{"provider": "local", "hashed_password": "x",
                                              "password_changed_at": changed, "must_change_password": False}]}
    seed_users(fake_db, user)
    old = raw_token({"sub": ADMIN_USER["_id"], "iat": int(time.time()) - 3600})
    new = raw_token({"sub": ADMIN_USER["_id"], "iat": int(time.time())})
    assert me(client(), old).status_code == 401
    assert me(client(), new).status_code == 200


def test_BE11_token_same_second_as_password_change_accepted(fake_db):
    now = datetime.now(timezone.utc)
    user = {**ADMIN_USER, "auth_providers": [{"provider": "local", "hashed_password": "x",
                                              "password_changed_at": now.replace(tzinfo=None, microsecond=900000),
                                              "must_change_password": False}]}
    seed_users(fake_db, user)
    same_second = raw_token({"sub": ADMIN_USER["_id"], "iat": int(now.replace(microsecond=900000).timestamp())})
    assert me(client(), same_second).status_code == 200            # comparación truncada al segundo


def test_BE11_all_auth_failures_same_401(fake_db):
    seed_users(fake_db, {**ADMIN_USER}, {**EDITOR_USER, "status": "disabled"})
    c = client()
    cases = {
        "sin token": {},
        "firma inválida": raw_token({"sub": ADMIN_USER["_id"]}, secret="otro-secreto"),
        "vencido": raw_token({"sub": ADMIN_USER["_id"]}, exp_delta=timedelta(minutes=-5)),
        "sin sub": raw_token({"foo": "bar"}),
        "usuario inexistente": raw_token({"sub": "6600000000000000000000ff"}),
        "usuario deshabilitado": raw_token({"sub": EDITOR_USER["_id"]}),
        "basura": {"Authorization": "Bearer no.es.un.jwt"},
    }
    bodies = set()
    for name, headers in cases.items():
        r = me(c, headers)
        assert r.status_code == 401, name
        assert r.headers["www-authenticate"] == "Bearer", name
        bodies.add(r.text if name != "sin token" else "Could not validate credentials")
    assert len({b for n, h in cases.items() if n != "sin token" for b in [me(c, h).text]}) == 1


def test_BE11_login_accepts_email_case_insensitive(fake_db):
    seed_users(fake_db, user_with_password({**ADMIN_USER, "username": "admin"}, PASSWORD))
    c = client()
    for login in ("admin@slepllanquihue.cl", "  ADMIN@SlepLlanquihue.CL ", "admin"):
        r = c.post("/api/auth/login", json={"username": login, "password": PASSWORD})
        assert r.status_code == 200, login


@pytest.mark.parametrize("status", ["invited", "disabled"])
def test_BE11_invited_and_disabled_cannot_login(fake_db, status):
    seed_users(fake_db, user_with_password(ADMIN_USER, PASSWORD, status=status))
    c = client()
    bad = c.post("/api/auth/login", json={"username": "admin@slepllanquihue.cl", "password": PASSWORD})
    wrong = c.post("/api/auth/login", json={"username": "nadie@slepllanquihue.cl", "password": "x"})
    assert bad.status_code == wrong.status_code == 401
    assert bad.json() == wrong.json()                              # idéntico a credenciales erróneas


@pytest.mark.parametrize("sub", [{"$ne": None}, "$ne", "'; DROP TABLE users;--", "x" * 500, 12345])
def test_BE11_malformed_sub_returns_401(fake_db, sub):
    seed_users(fake_db, ADMIN_USER)
    assert me(client(), raw_token({"sub": sub})).status_code == 401


def test_BE11_login_updates_last_login_at(fake_db):
    seed_users(fake_db, user_with_password(ADMIN_USER, PASSWORD))
    assert fake_db.users.docs[0]["last_login_at"] is None
    client().post("/api/auth/login", json={"username": "admin@slepllanquihue.cl", "password": PASSWORD})
    assert fake_db.users.docs[0]["last_login_at"] is not None


def test_BE11_login_body_rejects_operator_objects(fake_db):
    seed_users(fake_db, user_with_password(ADMIN_USER, PASSWORD))
    r = client().post("/api/auth/login", json={"username": {"$ne": None}, "password": {"$ne": None}})
    assert r.status_code == 422
