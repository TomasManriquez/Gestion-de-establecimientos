"""
test_BE28_users_detail_and_edit.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: US-21 · Ver y editar un usuario (R1, C19, T1, T5)
"""
import copy
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from tests.conftest import (ADMIN_USER, SAMPLE_ESTABLISHMENT, prepare_org, bearer_for, _user, seed_users)

UID = "6600000000000000000000e1"


@pytest.fixture
def ctx(fake_db):
    ids = prepare_org(fake_db, ADMIN_USER)
    fake_db.establishments.seed(copy.deepcopy(SAMPLE_ESTABLISHMENT))
    seed_users(fake_db, _user(UID, "ana.perez@slepllanquihue.cl", "Ana", "Pérez", [("datos", "editor")], unit_id=ids["AF-TI"]),
               _user("6600000000000000000000e2", "otro@slepllanquihue.cl", "Otro", "Usuario", [], unit_id=ids["AF-FIN"]))
    from app.main import app
    return TestClient(app, raise_server_exceptions=True), ids, bearer_for(ADMIN_USER), fake_db


def test_BE28_get_user_detail(ctx):
    c, ids, h, db = ctx
    r = c.get(f"/api/users/{UID}", headers=h)
    assert r.status_code == 200
    u = r.json()
    assert u["email"] == "ana.perez@slepllanquihue.cl" and u["personal_phone"] == "+56911112222"
    assert u["access"][0]["platform_id"] == "datos"
    assert "hashed_password" not in r.text and "$2b$" not in r.text
    assert u["auth_providers"][0]["provider"] == "local" and "hashed_password" not in u["auth_providers"][0]


def test_BE28_patch_returns_updated_document(ctx):
    c, ids, h, db = ctx
    r = c.patch(f"/api/users/{UID}", json={"first_name": "Ana María", "work_extension": "4599"}, headers=h)
    assert r.status_code == 200
    u = r.json()
    assert u["first_name"] == "Ana María" and u["work_extension"] == "4599" and u["last_name"] == "Pérez"
    assert u["updated_by"] == ADMIN_USER["_id"] and u["updated_at"] is not None


def test_BE28_empty_patch_is_harmless(ctx):
    c, ids, h, db = ctx
    r = c.patch(f"/api/users/{UID}", json={}, headers=h)
    assert r.status_code == 200 and r.json()["first_name"] == "Ana"


def test_BE28_invalid_combination_leaves_document_unchanged(ctx):
    c, ids, h, db = ctx
    before = copy.deepcopy(next(d for d in db.users.docs if str(d["_id"]) == UID))
    # pasar a establecimiento sin rbd ni cargos
    assert c.patch(f"/api/users/{UID}", json={"is_slep_staff": False}, headers=h).status_code == 422
    # rbd sin cambiar de modo (sigue siendo funcionario SLEP)
    assert c.patch(f"/api/users/{UID}", json={"rbd": "7722"}, headers=h).status_code == 422
    # unit inexistente
    r = c.patch(f"/api/users/{UID}", json={"unit_id": "6600000000000000000000ee"}, headers=h)
    assert r.status_code == 422 and r.json()["detail"][0]["field"] == "unit_id"
    after = next(d for d in db.users.docs if str(d["_id"]) == UID)
    assert after == before                                                    # ninguna escritura


def test_BE28_switching_mode_clears_the_other_mode_fields(ctx):
    c, ids, h, db = ctx
    r = c.patch(f"/api/users/{UID}", json={"is_slep_staff": False, "rbd": "7722", "positions": ["DOCENTE"]}, headers=h)
    assert r.status_code == 200
    u = r.json()
    assert u["is_slep_staff"] is False and u["unit_id"] is None and u["rbd"] == "7722" and u["positions"] == ["DOCENTE"]
    back = c.patch(f"/api/users/{UID}", json={"is_slep_staff": True, "unit_id": ids["AF-TI"]}, headers=h).json()
    assert back["is_slep_staff"] is True and back["rbd"] is None and back["positions"] == [] and back["unit_id"] == ids["AF-TI"]


@pytest.mark.parametrize("field,value", [
    ("access", [{"platform_id": "iam", "role": "admin"}]), ("status", "active"),
    ("auth_providers", []), ("hashed_password", "x"), ("created_by", UID), ("_id", UID),
])
def test_BE28_patch_forbids_access_status_and_providers(ctx, field, value):
    c, ids, h, db = ctx
    assert c.patch(f"/api/users/{UID}", json={field: value}, headers=h).status_code == 422


def test_BE28_email_change_conflict_409(ctx):
    c, ids, h, db = ctx
    r = c.patch(f"/api/users/{UID}", json={"email": "OTRO@slepllanquihue.cl"}, headers=h)
    assert r.status_code == 409 and r.json()["detail"]["field"] == "email"
    ok = c.patch(f"/api/users/{UID}", json={"email": "ana.nueva@slepllanquihue.cl"}, headers=h)
    assert ok.status_code == 200 and ok.json()["email"] == "ana.nueva@slepllanquihue.cl"
    assert ok.json()["_id"] == UID                                            # el sub del JWT (C6) no cambia
    assert c.get("/api/auth/me", headers=bearer_for({"_id": UID})).status_code == 200


def test_BE28_static_routes_not_shadowed_by_id_route(ctx):
    c, ids, h, db = ctx
    r = c.get("/api/users/me", headers=h)
    assert r.status_code == 200 and r.json()["email"] == ADMIN_USER["email"]      # no es "User me not found"


def test_BE28_invalid_id_is_404(ctx):
    c, ids, h, db = ctx
    for bad in ("no-es-id", "123", "6600000000000000000000ee", "%24ne"):
        assert c.get(f"/api/users/{bad}", headers=h).status_code == 404, bad
        assert c.patch(f"/api/users/{bad}", json={"first_name": "X"}, headers=h).status_code == 404, bad
        assert c.post(f"/api/users/{bad}/disable", headers=h).status_code == 404, bad
