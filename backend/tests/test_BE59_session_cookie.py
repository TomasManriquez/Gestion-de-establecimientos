"""
test_BE59_session_cookie.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: S3 · Cookie `HttpOnly` en lugar de `localStorage` (ADR-016)

Verifica que:
  - login, login-form, Google y cambio de contraseña entregan el JWT SOLO en `Set-Cookie`
    (HttpOnly, SameSite=Strict, Path=/api, Max-Age = vigencia; Secure cuando PUBLIC_BASE_URL es https)
    y nunca en el cuerpo; la respuesta no se cachea
  - la cookie autentica por sí sola; una cookie falsificada, vencida o revocada da el mismo 401
  - con cookie, toda petición que no sea de solo lectura exige `Origin` = PUBLIC_BASE_URL (403 si
    falta o es ajeno): protege de un sitio hermano, que SameSite no frena
  - la cabecera `Authorization: Bearer` sigue sirviendo a clientes que no son navegador, sin chequeo
    de Origen (no es una credencial ambiental), y tiene prioridad sobre la cookie
  - logout borra la cookie, corta todas las sesiones y no falla con token malo; un logout con
    Origen ajeno es 403 y no revoca nada
"""
import time
from datetime import datetime, timedelta, timezone

from unittest.mock import patch

import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from tests.conftest import (ADMIN_USER, EDITOR_USER, SESSION_COOKIE, bearer_for, seed_users, session_headers,
                            user_with_password)

PASSWORD = "contrasena-larga-de-prueba-1"
GOOD_ORIGIN = {"Origin": "http://localhost:5173"}          # = PUBLIC_BASE_URL de los tests (conftest)


@pytest.fixture
def ctx(fake_db):
    seed_users(fake_db, user_with_password(EDITOR_USER, PASSWORD))
    from app.main import app
    return TestClient(app), fake_db


def login(c, **kw):
    return c.post("/api/auth/login", json={"username": EDITOR_USER["email"], "password": PASSWORD}, **kw)


def client_with_cookie(app, value):
    c = TestClient(app)
    c.cookies.set(SESSION_COOKIE, value, path="/api")
    return c


def set_cookie_header(r):
    return next(v for k, v in r.headers.multi_items() if k.lower() == "set-cookie")


# ─── emisión ─────────────────────────────────────────────────────────────────

def test_BE59_login_sets_httponly_strict_cookie_and_no_token_in_body(ctx):
    c, db = ctx
    r = login(c)
    assert r.status_code == 200
    header = set_cookie_header(r).lower()
    assert header.startswith(f"{SESSION_COOKIE}=")
    assert "httponly" in header and "samesite=strict" in header and "path=/api" in header
    assert f"max-age={settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60}" in header
    assert "secure" not in header.replace("samesite", "")          # http://localhost de desarrollo
    assert r.json() == {"expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60}
    token = r.cookies[SESSION_COOKIE]
    assert token not in r.text and "access_token" not in r.text
    assert r.headers["cache-control"] == "no-store"
    assert jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])["sub"] == EDITOR_USER["_id"]


def test_BE59_cookie_is_secure_when_the_public_url_is_https(ctx, monkeypatch):
    c, db = ctx
    monkeypatch.setattr(settings, "SESSION_COOKIE_SECURE", True)
    assert "secure" in set_cookie_header(login(c)).lower().replace("samesite", "")


def test_BE59_secure_flag_follows_public_base_url():
    from app.config import Settings
    from tests.test_BE14_settings_fail_fast import VALID_ENV
    gmail = {**VALID_ENV, "MAIL_MODE": "gmail", "PUBLIC_BASE_URL": "https://gestion.slepllanquihue.cl",
             "GMAIL_SENDER_ADDRESS": "no-responder@slepllanquihue.cl", "GMAIL_REFRESH_TOKEN": "x",
             "GOOGLE_CLIENT_ID": "id", "GOOGLE_CLIENT_SECRET": "s"}
    assert Settings(gmail).SESSION_COOKIE_SECURE is True
    assert Settings(VALID_ENV).SESSION_COOKIE_SECURE is False


@pytest.mark.parametrize("path,kind", [("/api/auth/login", "json"), ("/api/auth/login-form", "form")])
def test_BE59_both_password_logins_use_the_cookie(ctx, path, kind):
    c, db = ctx
    creds = {"username": EDITOR_USER["email"], "password": PASSWORD}
    r = c.post(path, json=creds) if kind == "json" else c.post(path, data=creds)
    assert r.status_code == 200 and SESSION_COOKIE in r.cookies and set(r.json()) == {"expires_in"}


def test_BE59_password_change_rotates_the_cookie(ctx):
    c, db = ctx
    with patch("app.auth.auth_service.time.time", return_value=time.time() - 30):   # login «de hace 30 s»: sin sleep ni depender del reloj
        first = login(c)
    r = c.post("/api/auth/password", headers=GOOD_ORIGIN,
               json={"current_password": PASSWORD, "new_password": "otra-contrasena-larga-22"})
    assert r.status_code == 200 and set(r.json()) == {"expires_in"}
    assert r.cookies[SESSION_COOKIE] != first.cookies[SESSION_COOKIE]
    assert c.get("/api/auth/me").status_code == 200                  # la jarra ya trae la cookie nueva
    old = TestClient(c.app).get("/api/auth/me", headers=session_headers(first))
    assert old.status_code == 401                                    # la anterior quedó cortada


# ─── la cookie autentica ─────────────────────────────────────────────────────

def test_BE59_cookie_alone_authenticates(ctx):
    c, db = ctx
    assert c.get("/api/auth/me").status_code == 401                  # sin sesión
    login(c)
    r = c.get("/api/auth/me")
    assert r.status_code == 200 and r.json()["email"] == EDITOR_USER["email"]


@pytest.mark.parametrize("value", ["basura", "a.b.c", "x" * 3000, ""])
def test_BE59_forged_cookie_gives_the_uniform_401(fake_db, value):
    seed_users(fake_db, EDITOR_USER)
    from app.main import app
    r = client_with_cookie(app, value).get("/api/auth/me")
    assert r.status_code == 401 and r.json() == {"detail": "Could not validate credentials"}


def test_BE59_cookie_signed_with_another_key_or_expired_is_rejected(fake_db):
    seed_users(fake_db, EDITOR_USER)
    from app.main import app
    now = int(time.time())
    for key, exp in (("otra-clave-de-al-menos-32-caracteres-xx", 300), (settings.JWT_SECRET, -300)):
        token = jwt.encode({"sub": EDITOR_USER["_id"], "iat": now, "exp": datetime.now(timezone.utc) + timedelta(seconds=exp)},
                           key, algorithm="HS256")
        assert client_with_cookie(app, token).get("/api/auth/me").status_code == 401


def test_BE59_disabled_user_cookie_is_rejected(ctx):
    c, db = ctx
    login(c)
    db.users.docs[0]["status"] = "disabled"
    assert c.get("/api/auth/me").status_code == 401


# ─── CSRF: Origin ────────────────────────────────────────────────────────────

WRITE = ("PATCH", "/api/users/me", {"work_extension": "1234"})


def test_BE59_unsafe_request_with_cookie_requires_the_trusted_origin(ctx):
    c, db = ctx
    login(c)
    method, path, body = WRITE
    missing = c.request(method, path, json=body)
    wrong = c.request(method, path, json=body, headers={"Origin": "https://evil.example"})
    sibling = c.request(method, path, json=body, headers={"Origin": "http://localhost:5173.evil.example"})
    for r in (missing, wrong, sibling):
        assert r.status_code == 403 and r.json()["detail"]["code"] == "untrusted_origin"
    assert db.users.docs[0]["work_extension"] == EDITOR_USER["work_extension"]            # nada se escribió
    ok = c.request(method, path, json=body, headers=GOOD_ORIGIN)
    assert ok.status_code == 200 and db.users.docs[0]["work_extension"] == "1234"


def test_BE59_read_requests_do_not_need_origin(ctx):
    c, db = ctx
    login(c)
    assert c.get("/api/auth/me", headers={"Origin": "https://evil.example"}).status_code == 200


def test_BE59_bearer_header_is_not_subject_to_the_origin_check(fake_db):
    seed_users(fake_db, EDITOR_USER)
    from app.main import app
    r = TestClient(app).patch("/api/users/me", json={"work_extension": "4321"}, headers=bearer_for(EDITOR_USER))
    assert r.status_code == 200


def test_BE59_authorization_header_wins_over_the_cookie(ctx):
    c, db = ctx
    login(c)                                                        # cookie válida en la jarra
    r = c.get("/api/auth/me", headers={"Authorization": "Bearer basura"})
    assert r.status_code == 401


# ─── logout ──────────────────────────────────────────────────────────────────

def test_BE59_logout_clears_the_cookie_and_revokes_every_session(ctx):
    c, db = ctx
    r1 = login(c)
    r = c.post("/api/auth/logout", headers=GOOD_ORIGIN)
    assert r.status_code == 204 and r.content == b""
    cleared = set_cookie_header(r).lower()
    assert cleared.startswith(f"{SESSION_COOKIE}=") and ("max-age=0" in cleared or "expires=" in cleared)
    assert "path=/api" in cleared and "httponly" in cleared
    assert c.get("/api/auth/me").status_code == 401                              # la jarra ya no la envía
    assert TestClient(c.app).get("/api/auth/me", headers=session_headers(r1)).status_code == 401   # y el token quedó revocado
    assert db.users.docs[0]["sessions_revoked_at"] is not None


def test_BE59_logout_with_a_foreign_origin_is_403_and_revokes_nothing(ctx):
    c, db = ctx
    login(c)
    r = c.post("/api/auth/logout", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    assert "sessions_revoked_at" not in db.users.docs[0]
    assert c.get("/api/auth/me").status_code == 200


def test_BE59_logout_never_fails_for_the_one_logging_out(ctx):
    c, db = ctx
    for headers, cookie in (({}, None), ({"Authorization": "Bearer basura"}, None), (GOOD_ORIGIN, "basura")):
        anon = client_with_cookie(c.app, cookie) if cookie else TestClient(c.app)
        r = anon.post("/api/auth/logout", headers=headers)
        assert r.status_code == 204 and SESSION_COOKIE in set_cookie_header(r)
    assert "sessions_revoked_at" not in db.users.docs[0]


def test_BE59_logout_with_bearer_still_works_for_non_browser_clients(fake_db):
    seed_users(fake_db, ADMIN_USER)
    from app.main import app
    c = TestClient(app)
    h = bearer_for(ADMIN_USER)
    assert c.post("/api/auth/logout", headers=h).status_code == 204
    assert c.get("/api/auth/me", headers=h).status_code == 401
