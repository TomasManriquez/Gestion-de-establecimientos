"""
test_INT07_users_no_secret_leak.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: transversal T4 · Ninguna respuesta de la feature incluye hashed_password ni token_hash, y
personal_phone solo llega al admin global y al propio usuario. Mismo patrón que INT02: se recorre
el JSON completo de cada respuesta.
"""
import re
import pytest
from fastapi.testclient import TestClient
from tests.conftest import (ADMIN_USER, EDITOR_USER, VIEWER_USER, NO_DATOS_USER, prepare_org, bearer_for,
                            user_with_password, seed_users, _user)

PHONE = "+56911112222"
SECRET_KEYS = {"hashed_password", "token_hash", "password_hash", "refresh_token"}


def walk(value, path="$"):
    if isinstance(value, dict):
        for k, v in value.items():
            yield path + "." + k, k, v
            yield from walk(v, path + "." + k)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from walk(v, f"{path}[{i}]")


@pytest.fixture
def ctx(fake_db):
    prepare_org(fake_db, user_with_password(ADMIN_USER, "una-clave-larga-de-prueba"), EDITOR_USER, VIEWER_USER, NO_DATOS_USER)
    from app.main import app
    return TestClient(app, raise_server_exceptions=True), fake_db


ADMIN_READS = [
    "/api/users", f"/api/users/{ADMIN_USER['_id']}", f"/api/users/{EDITOR_USER['_id']}", "/api/users/me",
    "/api/auth/me", "/api/units", "/api/units/tree?expand=head", "/api/platforms", "/api/auth/password-policy",
]


@pytest.mark.parametrize("path", ADMIN_READS)
def test_INT07_no_hash_or_secret_keys_in_any_response(ctx, path):
    c, db = ctx
    r = c.get(path, headers=bearer_for(ADMIN_USER))
    assert r.status_code == 200, path
    leaked = [p for p, k, v in walk(r.json()) if k in SECRET_KEYS]
    assert leaked == [], f"{path} expone claves secretas: {leaked}"
    assert not re.search(r"\$2[aby]\$\d\d\$", r.text), f"{path} expone un hash bcrypt"


def test_INT07_write_responses_never_leak_hashes(ctx):
    c, db = ctx
    h = bearer_for(ADMIN_USER)
    uid = EDITOR_USER["_id"]
    responses = [
        c.patch(f"/api/users/{uid}", json={"first_name": "Nuevo"}, headers=h),
        c.post(f"/api/users/{uid}/disable", headers=h),
        c.post(f"/api/users/{uid}/enable", headers=h),
        c.put(f"/api/users/{uid}/access/selloverde", json={"role": "viewer"}, headers=h),
        c.delete(f"/api/users/{uid}/access/selloverde", headers=h),
        c.patch("/api/users/me", json={"work_extension": "5555"}, headers=h),
        c.post("/api/users", json={"email": "nuevo.usuario@slepllanquihue.cl", "first_name": "N", "last_name": "U",
                                   "is_slep_staff": True, "unit_id": str(db.units.docs[0]["_id"])}, headers=h),
    ]
    for r in responses:
        assert r.status_code in (200, 201), r.text
        assert not [p for p, k, v in walk(r.json()) if k in SECRET_KEYS]
        assert not re.search(r"\$2[aby]\$", r.text)


def test_INT07_login_and_password_change_responses_have_only_the_token(ctx):
    c, db = ctx
    r = c.post("/api/auth/login", json={"username": ADMIN_USER["email"], "password": "una-clave-larga-de-prueba"})
    assert set(r.json()) == {"access_token", "token_type"}
    ch = c.post("/api/auth/password", json={"current_password": "una-clave-larga-de-prueba", "new_password": "otra-frase-larga-xyz-1"},
                headers={"Authorization": "Bearer " + r.json()["access_token"]})
    assert set(ch.json()) == {"access_token", "token_type"}


def test_INT07_personal_phone_only_for_iam_admin_and_owner(ctx):
    c, db = ctx
    # el admin global lo ve en el detalle y en el suyo; nunca en el listado
    assert c.get(f"/api/users/{EDITOR_USER['_id']}", headers=bearer_for(ADMIN_USER)).json()["personal_phone"] == PHONE
    assert PHONE not in c.get("/api/users", headers=bearer_for(ADMIN_USER)).text
    # el propio usuario ve el suyo
    assert c.get("/api/users/me", headers=bearer_for(EDITOR_USER)).json()["personal_phone"] == PHONE
    # nadie más, por ninguna ruta que ya tenga
    for viewer in (EDITOR_USER, VIEWER_USER, NO_DATOS_USER):
        for path in ("/api/units", "/api/units/tree?expand=head", "/api/auth/me", "/api/establishments",
                     f"/api/users/{ADMIN_USER['_id']}"):
            r = c.get(path, headers=bearer_for(viewer))
            assert PHONE not in r.text or path == "/api/users/me", f"{viewer['email']} ve un teléfono en {path}"
