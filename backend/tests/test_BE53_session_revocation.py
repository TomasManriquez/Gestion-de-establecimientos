"""
test_BE53_session_revocation.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: SEC-3 · Revocación de sesiones sin estado (`sessions_revoked_at`)

Verifica que:
  - POST /logout corta TODAS las sesiones de la persona (dos tokens vigentes quedan inválidos)
  - sirve a una cuenta de Google, que no tiene `password_changed_at`
  - POST /logout devuelve 204 aunque no haya token, esté vencido, malformado o ya revocado
  - un logout no afecta a otras personas
  - un token emitido DESPUÉS del logout sirve
  - desactivar a una persona fija el corte: reactivarla NO revive los tokens anteriores
  - cambiar la contraseña sigue cortando las sesiones previas y entrega un token válido
"""
import time
from datetime import datetime, timedelta, timezone
import jwt
from fastapi.testclient import TestClient
from app.config import settings
from tests.conftest import (ADMIN_USER, EDITOR_USER, _user, bearer_for, prepare_org, run, seed_users, session_headers,
                            user_with_password)

GOOGLE_USER = _user("6600000000000000000000b1", "google@slepllanquihue.cl", "Gina", "Google", [("datos", "viewer")],
                    auth_providers=[{"provider": "google", "subject": "1234567890"}])


def client():
    from app.main import app
    return TestClient(app)


def token_at(user, iat):
    body = {"sub": user["_id"], "iat": iat, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
    return {"Authorization": "Bearer " + jwt.encode(body, settings.JWT_SECRET, algorithm="HS256")}


def me(c, headers):
    return c.get("/api/auth/me", headers=headers).status_code


def test_BE53_logout_cuts_every_session_of_a_google_account(fake_db):
    seed_users(fake_db, GOOGLE_USER)
    c = client()
    now = int(time.time())
    first, second = token_at(GOOGLE_USER, now - 30), token_at(GOOGLE_USER, now - 5)
    assert me(c, first) == me(c, second) == 200
    assert c.post("/api/auth/logout", headers=second).status_code == 204
    assert me(c, first) == me(c, second) == 401
    assert fake_db.users.docs[0]["sessions_revoked_at"] is not None


def test_BE53_token_just_issued_is_cut_by_an_immediate_logout(fake_db):
    seed_users(fake_db, GOOGLE_USER)
    c = client()
    headers = bearer_for(GOOGLE_USER)                      # iat = este mismo segundo
    assert c.post("/api/auth/logout", headers=headers).status_code == 204
    assert me(c, headers) == 401


def test_BE53_token_issued_after_logout_works(fake_db):
    seed_users(fake_db, GOOGLE_USER)
    c = client()
    assert c.post("/api/auth/logout", headers=bearer_for(GOOGLE_USER)).status_code == 204
    assert me(c, token_at(GOOGLE_USER, int(time.time()) + 2)) == 200


def test_BE53_logout_always_204(fake_db):
    seed_users(fake_db, GOOGLE_USER)
    c = client()
    stale = token_at(GOOGLE_USER, int(time.time()) - 30)
    assert c.post("/api/auth/logout").status_code == 204                                        # sin token
    assert c.post("/api/auth/logout", headers={"Authorization": "Bearer basura"}).status_code == 204
    assert c.post("/api/auth/logout", headers={"Authorization": "Basic abc"}).status_code == 204
    assert c.post("/api/auth/logout", headers=stale).status_code == 204
    assert c.post("/api/auth/logout", headers=stale).status_code == 204                          # ya revocado
    assert c.post("/api/auth/logout").content == b""


def test_BE53_logout_with_garbage_token_writes_nothing(fake_db):
    seed_users(fake_db, GOOGLE_USER)
    client().post("/api/auth/logout", headers={"Authorization": "Bearer basura"})
    assert "sessions_revoked_at" not in fake_db.users.docs[0]


def test_BE53_logout_does_not_affect_other_people(fake_db):
    seed_users(fake_db, GOOGLE_USER, EDITOR_USER)
    c = client()
    other = token_at(EDITOR_USER, int(time.time()) - 5)
    assert c.post("/api/auth/logout", headers=bearer_for(GOOGLE_USER)).status_code == 204
    assert me(c, other) == 200


def test_BE53_disable_then_enable_does_not_revive_old_tokens(fake_db):
    ids = prepare_org(fake_db, ADMIN_USER, GOOGLE_USER)
    c = client()
    admin = bearer_for(ADMIN_USER)
    old = token_at(GOOGLE_USER, int(time.time()) - 5)
    assert me(c, old) == 200
    assert c.post(f"/api/users/{GOOGLE_USER['_id']}/disable", headers=admin).status_code == 200
    assert me(c, old) == 401
    assert c.post(f"/api/users/{GOOGLE_USER['_id']}/enable", headers=admin).status_code == 200
    assert me(c, old) == 401, "reactivar no debe revivir un token anterior a la desactivación"
    assert me(c, token_at(GOOGLE_USER, int(time.time()) + 2)) == 200


def test_BE53_password_change_still_cuts_previous_sessions(fake_db):
    password, new = "contrasena-actual-muy-larga-1", "contrasena-nueva-muy-larga-22"
    seed_users(fake_db, user_with_password(EDITOR_USER, password))
    c = client()
    old = token_at(EDITOR_USER, int(time.time()) - 30)
    r = c.post("/api/auth/password", json={"current_password": password, "new_password": new}, headers=old)
    assert r.status_code == 200
    assert me(c, old) == 401
    assert me(c, session_headers(r)) == 200
