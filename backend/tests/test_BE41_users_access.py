"""
test_BE41_users_access.py
━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: US-34 · Otorgar y revocar rol por plataforma (R5, C12, C14, T5, T7)
"""
import pytest
from fastapi.testclient import TestClient
from tests.conftest import ADMIN_USER, VIEWER_USER, prepare_org, bearer_for, _user, seed_users

TARGET = _user("6600000000000000000000e9", "nuevo@slepllanquihue.cl", "Nuevo", "Usuario", [])


@pytest.fixture
def ctx(fake_db):
    prepare_org(fake_db, ADMIN_USER, VIEWER_USER, TARGET)
    from app.main import app
    return TestClient(app, raise_server_exceptions=True), bearer_for(ADMIN_USER), fake_db


def doc(db, uid):
    return next(d for d in db.users.docs if str(d["_id"]) == uid)


def test_BE41_grant_role(ctx):
    c, h, db = ctx
    r = c.put(f"/api/users/{TARGET['_id']}/access/datos", json={"role": "editor"}, headers=h)
    assert r.status_code == 200
    entry = r.json()["access"][0]
    assert entry["platform_id"] == "datos" and entry["role"] == "editor"
    assert entry["granted_at"] is not None and entry["granted_by"] == ADMIN_USER["_id"]
    # el efecto es inmediato: el usuario ya puede escribir en datos
    assert c.put("/api/establishments/7722", json={"name": "X"}, headers=bearer_for(TARGET)).status_code != 403


def test_BE41_role_validated_against_platform(ctx):
    c, h, db = ctx
    r = c.put(f"/api/users/{TARGET['_id']}/access/iam", json={"role": "editor"}, headers=h)
    assert r.status_code == 422 and r.json()["detail"][0]["code"] == "invalid_role"        # iam solo tiene admin
    assert c.put(f"/api/users/{TARGET['_id']}/access/datos", json={"role": "superuser"}, headers=h).status_code == 422
    assert c.put(f"/api/users/{TARGET['_id']}/access/no-existe", json={"role": "admin"}, headers=h).status_code == 404
    assert doc(db, TARGET["_id"])["access"] == []                                          # nada se escribió


def test_BE41_one_entry_per_platform(ctx):
    c, h, db = ctx
    c.put(f"/api/users/{TARGET['_id']}/access/datos", json={"role": "viewer"}, headers=h)
    c.put(f"/api/users/{TARGET['_id']}/access/datos", json={"role": "admin"}, headers=h)
    c.put(f"/api/users/{TARGET['_id']}/access/selloverde", json={"role": "editor"}, headers=h)
    access = doc(db, TARGET["_id"])["access"]
    assert sorted((a["platform_id"], a["role"]) for a in access) == [("datos", "admin"), ("selloverde", "editor")]


def test_BE41_last_iam_admin_cannot_lose_iam(ctx):
    c, h, db = ctx
    r = c.delete(f"/api/users/{ADMIN_USER['_id']}/access/iam", headers=h)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "last_admin"
    assert any(a["platform_id"] == "iam" for a in doc(db, ADMIN_USER["_id"])["access"])
    # con un segundo admin global sí se puede
    c.put(f"/api/users/{TARGET['_id']}/access/iam", json={"role": "admin"}, headers=h)
    assert c.delete(f"/api/users/{ADMIN_USER['_id']}/access/iam", headers=h).status_code == 200


def test_BE41_revoke_takes_effect_on_next_request(ctx):
    c, h, db = ctx
    assert c.get("/api/establishments", headers=bearer_for(VIEWER_USER)).status_code == 200
    r = c.delete(f"/api/users/{VIEWER_USER['_id']}/access/datos", headers=h)
    assert r.status_code == 200 and r.json()["access"] == []
    assert c.get("/api/establishments", headers=bearer_for(VIEWER_USER)).status_code == 403    # token vigente, sin acceso


def test_BE41_malformed_input_and_ids(ctx):
    c, h, db = ctx
    assert c.put(f"/api/users/{TARGET['_id']}/access/datos", json={"role": {"$ne": None}}, headers=h).status_code == 422
    assert c.put(f"/api/users/{TARGET['_id']}/access/datos", json={"role": "viewer", "granted_by": "x"}, headers=h).status_code == 422
    assert c.put("/api/users/no-es-id/access/datos", json={"role": "viewer"}, headers=h).status_code == 404
    assert c.delete("/api/users/6600000000000000000000ee/access/datos", headers=h).status_code == 404


def test_BE41_only_iam_admin(ctx):
    c, h, db = ctx
    assert c.put(f"/api/users/{TARGET['_id']}/access/datos", json={"role": "admin"}, headers=bearer_for(VIEWER_USER)).status_code == 403
