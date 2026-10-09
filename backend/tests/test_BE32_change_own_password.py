"""
test_BE32_change_own_password.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: US-25 · Cambiar mi contraseña (R7, R10, C16, C17)
"""
import time
import pytest
from fastapi.testclient import TestClient
from tests.conftest import ADMIN_USER, EDITOR_USER, seed_users, user_with_password, bearer_for

OLD, NEW = "una-clave-larga-de-prueba", "otra-frase-larga-y-distinta"


@pytest.fixture
def ctx(fake_db):
    seed_users(fake_db, user_with_password(EDITOR_USER, OLD))
    from app.main import app
    return TestClient(app, raise_server_exceptions=True), fake_db


def login(c, password):
    return c.post("/api/auth/login", json={"username": EDITOR_USER["email"], "password": password})


def change(c, headers, current=OLD, new=NEW):
    return c.post("/api/auth/password", json={"current_password": current, "new_password": new}, headers=headers)


def test_BE32_change_password_returns_fresh_token(ctx):
    c, db = ctx
    headers = {"Authorization": "Bearer " + login(c, OLD).json()["access_token"]}
    r = change(c, headers)
    assert r.status_code == 200 and r.json()["token_type"] == "bearer"
    local = db.users.docs[0]["auth_providers"][0]
    assert local["password_changed_at"] is not None and local["must_change_password"] is False
    assert login(c, NEW).status_code == 200 and login(c, OLD).status_code == 401           # la clave cambió de verdad
    assert c.get("/api/auth/me", headers={"Authorization": "Bearer " + r.json()["access_token"]}).status_code == 200


def test_BE32_wrong_current_password_is_not_401(ctx):
    """El interceptor del frontend cierra la sesión ante cualquier 401 (App.jsx:38)."""
    c, db = ctx
    headers = {"Authorization": "Bearer " + login(c, OLD).json()["access_token"]}
    r = change(c, headers, current="clave-actual-equivocada-123")
    assert r.status_code == 400 and r.status_code != 401
    assert r.json()["detail"]["code"] == "current_password_incorrect"
    assert login(c, OLD).status_code == 200                                                 # nada cambió


def test_BE32_old_token_rejected_new_token_valid(ctx):
    c, db = ctx
    old_headers = {"Authorization": "Bearer " + login(c, OLD).json()["access_token"]}
    time.sleep(1.1)                                                                          # el cambio cae en un segundo posterior al del login
    new_token = change(c, old_headers).json()["access_token"]
    assert c.get("/api/auth/me", headers=old_headers).status_code == 401                    # sesión anterior cerrada
    assert c.get("/api/auth/me", headers={"Authorization": f"Bearer {new_token}"}).status_code == 200


def test_BE32_policy_violation_returns_reasons(ctx):
    c, db = ctx
    headers = {"Authorization": "Bearer " + login(c, OLD).json()["access_token"]}
    before = db.users.docs[0]["auth_providers"][0]["hashed_password"]
    r = change(c, headers, new="corta")
    assert r.status_code == 422 and {v["code"] for v in r.json()["detail"]} == {"min_length"}
    r = change(c, headers, new="editor.editor-es-mi-correo")                                  # contiene el local-part del correo
    assert r.status_code == 422 and "context_word" in {v["code"] for v in r.json()["detail"]}
    assert db.users.docs[0]["auth_providers"][0]["hashed_password"] == before


def test_BE32_google_only_user_gets_409(fake_db):
    seed_users(fake_db, {**EDITOR_USER, "auth_providers": [{"provider": "google", "subject": "1", "linked_at": None}]})
    from app.main import app
    c = TestClient(app)
    r = change(c, bearer_for(EDITOR_USER))
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_local_password"


def test_BE32_requires_authentication_and_rejects_extra_fields(ctx):
    c, db = ctx
    assert c.post("/api/auth/password", json={"current_password": OLD, "new_password": NEW}).status_code == 401
    headers = {"Authorization": "Bearer " + login(c, OLD).json()["access_token"]}
    assert c.post("/api/auth/password", json={"current_password": OLD, "new_password": NEW, "user_id": "x"}, headers=headers).status_code == 422
    assert c.post("/api/auth/password", json={"current_password": {"$ne": None}, "new_password": NEW}, headers=headers).status_code == 422


def test_BE32_over_72_bytes_is_422_not_500(ctx):
    c, db = ctx
    headers = {"Authorization": "Bearer " + login(c, OLD).json()["access_token"]}
    r = change(c, headers, new="ñ" * 40)                                                      # 40 caracteres = 80 bytes
    assert r.status_code == 422 and "max_bytes" in {v["code"] for v in r.json()["detail"]}
