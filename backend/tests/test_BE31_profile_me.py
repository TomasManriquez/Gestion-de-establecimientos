"""
test_BE31_profile_me.py
━━━━━━━━━━━━━━━━━━━━━━
Tarea: US-24 · Ver y editar mi perfil (R10, C19, T1, T4)
"""
import pytest
from fastapi.testclient import TestClient
from tests.conftest import (ADMIN_USER, VIEWER_USER, NO_DATOS_USER, EDITOR_USER, prepare_org, seed_users, bearer_for)


@pytest.fixture
def ctx(fake_db):
    prepare_org(fake_db, ADMIN_USER, VIEWER_USER, NO_DATOS_USER, EDITOR_USER)
    from app.main import app
    return TestClient(app, raise_server_exceptions=True), fake_db


def test_BE31_get_me_for_any_authenticated_user(ctx):
    c, db = ctx
    for user in (ADMIN_USER, VIEWER_USER, NO_DATOS_USER):           # incluso sin acceso a `datos`
        r = c.get("/api/users/me", headers=bearer_for(user))
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == user["email"] and body["personal_phone"] == "+56911112222"    # su propio teléfono
        assert body["_id"] == user["_id"]
    assert c.get("/api/users/me").status_code == 401


def test_BE31_patch_me_updates_phone_and_extension(ctx):
    c, db = ctx
    r = c.patch("/api/users/me", json={"personal_phone": "+56998765432", "work_extension": "7788"}, headers=bearer_for(VIEWER_USER))
    assert r.status_code == 200
    assert r.json()["personal_phone"] == "+56998765432" and r.json()["work_extension"] == "7788"
    only_one = c.patch("/api/users/me", json={"work_extension": "9999"}, headers=bearer_for(VIEWER_USER)).json()
    assert only_one["work_extension"] == "9999" and only_one["personal_phone"] == "+56998765432"     # el otro no se pierde


@pytest.mark.parametrize("field,value", [
    ("access", [{"platform_id": "iam", "role": "admin"}]), ("status", "disabled"), ("unit_id", "6600000000000000000000f1"),
    ("email", "otro@slepllanquihue.cl"), ("first_name", "Hacker"), ("rbd", "7722"), ("positions", ["DIRECTOR"]),
    ("is_slep_staff", False), ("hashed_password", "x"), ("auth_providers", []), ("created_by", "x"), ("_id", "x"),
])
def test_BE31_patch_me_rejects_privileged_fields(ctx, field, value):
    c, db = ctx
    ignore = {"last_activity_at"}                                    # cambia en cada request autenticada, por diseño
    snap = lambda: {k: v for k, v in [d for d in db.users.docs if str(d["_id"]) == VIEWER_USER["_id"]][0].items() if k not in ignore}
    before = snap()
    r = c.patch("/api/users/me", json={field: value}, headers=bearer_for(VIEWER_USER))
    assert r.status_code == 422                                      # asignación masiva imposible
    assert snap() == before


def test_BE31_patch_me_validates_formats_and_operators(ctx):
    c, db = ctx
    for body in ({"personal_phone": "12345"}, {"work_extension": "ab"}, {"personal_phone": {"$ne": None}},
                 {"work_extension": {"$gt": ""}}, {"personal_phone": "+5691234567" + "8" * 20}):
        assert c.patch("/api/users/me", json=body, headers=bearer_for(VIEWER_USER)).status_code == 422


def test_BE31_me_never_contains_hashes(ctx):
    c, db = ctx
    text = c.get("/api/users/me", headers=bearer_for(ADMIN_USER)).text
    assert "hashed_password" not in text and "token_hash" not in text and "$2b$" not in text


def test_BE31_personal_phone_visible_only_to_owner_and_iam_admin(ctx):
    c, db = ctx
    vid = VIEWER_USER["_id"]
    assert c.get(f"/api/users/{vid}", headers=bearer_for(ADMIN_USER)).json()["personal_phone"] == "+56911112222"   # admin global
    assert c.get(f"/api/users/{vid}", headers=bearer_for(EDITOR_USER)).status_code == 403                          # otro usuario
    assert "personal_phone" not in c.get("/api/users", headers=bearer_for(ADMIN_USER)).text                       # nunca en el listado
    for path in ("/api/units/tree", "/api/units", "/api/auth/me", "/api/establishments"):
        assert "+56911112222" not in c.get(path, headers=bearer_for(EDITOR_USER)).text, path


def test_BE31_auth_me_additive_contract(ctx):
    """US-41 (parte backend): conserva username, full_name y role; agrega id, email y access."""
    c, db = ctx
    body = c.get("/api/auth/me", headers=bearer_for(VIEWER_USER)).json()
    assert body["role"] == "viewer" and body["full_name"] == "Vera Lectura" and body["email"] == VIEWER_USER["email"]
    assert body["access"] == [{"platform_id": "datos", "role": "viewer"}]
    assert c.get("/api/auth/me", headers=bearer_for(NO_DATOS_USER)).json()["role"] == "none"       # Q9
