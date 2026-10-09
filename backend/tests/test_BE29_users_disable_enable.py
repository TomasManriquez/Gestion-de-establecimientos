"""
test_BE29_users_disable_enable.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: US-22 · Desactivar y reactivar usuarios, soft delete (R1, R5, C9, T5, T7)
"""
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from tests.conftest import (ADMIN_USER, EDITOR_USER, prepare_org, bearer_for, _user, seed_users, user_with_password)

A2 = _user("6600000000000000000000aa", "admin2@slepllanquihue.cl", "Segundo", "Admin", [("iam", "admin")])


@pytest.fixture
def ctx(fake_db):
    ids = prepare_org(fake_db, ADMIN_USER, A2, EDITOR_USER)
    from app.main import app
    return TestClient(app, raise_server_exceptions=True), ids, bearer_for(ADMIN_USER), fake_db


def stored(db, uid):
    return next(d for d in db.users.docs if str(d["_id"]) == uid)


def test_BE29_disable_sets_status_and_blocks_session(ctx):
    c, ids, h, db = ctx
    editor_headers = bearer_for(EDITOR_USER)
    assert c.get("/api/establishments", headers=editor_headers).status_code == 200
    r = c.post(f"/api/users/{EDITOR_USER['_id']}/disable", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "disabled" and r.json()["disabled_at"] is not None
    assert c.get("/api/establishments", headers=editor_headers).status_code == 401      # token aún vigente, sesión cortada


def test_BE29_admin_cannot_disable_self(ctx):
    c, ids, h, db = ctx
    r = c.post(f"/api/users/{ADMIN_USER['_id']}/disable", headers=h)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "self_disable"
    assert stored(db, ADMIN_USER["_id"])["status"] == "active"


@pytest.mark.asyncio
async def test_BE29_last_iam_admin_cannot_be_disabled(fake_db):
    """Invariante de servicio: aunque el actor no sea el propio admin (por ejemplo en una operación
    masiva), no se puede dejar al sistema sin ningún iam/admin activo."""
    from app.users.users_entity import UserConflict
    from app.users.users_service import users_service
    seed_users(fake_db, ADMIN_USER, A2)
    await users_service.disable(A2["_id"], actor_id=ADMIN_USER["_id"])                  # queda 1: permitido
    with pytest.raises(UserConflict) as exc:
        await users_service.disable(ADMIN_USER["_id"], actor_id="6600000000000000000000ff")
    assert exc.value.code == "last_admin"
    assert stored(fake_db, ADMIN_USER["_id"])["status"] == "active"


def test_BE29_last_iam_admin_cannot_lose_iam_access(ctx):
    c, ids, h, db = ctx
    assert c.delete(f"/api/users/{A2['_id']}/access/iam", headers=h).status_code == 200      # queda 1
    r = c.delete(f"/api/users/{ADMIN_USER['_id']}/access/iam", headers=h)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "last_admin"


def test_BE29_enable_restores_active_or_invited(ctx):
    c, ids, h, db = ctx
    # con contraseña local -> active
    stored(db, EDITOR_USER["_id"])["auth_providers"][0]["hashed_password"] = "$2b$04$hashdeprueba"
    c.post(f"/api/users/{EDITOR_USER['_id']}/disable", headers=h)
    r = c.post(f"/api/users/{EDITOR_USER['_id']}/enable", headers=h)
    assert r.json()["status"] == "active" and r.json()["disabled_at"] is None
    # sin ninguna credencial (nunca definió contraseña) -> invited
    stored(db, A2["_id"])["auth_providers"] = []
    c.post(f"/api/users/{A2['_id']}/disable", headers=h)
    assert c.post(f"/api/users/{A2['_id']}/enable", headers=h).json()["status"] == "invited"
    # con Google vinculado -> active
    stored(db, A2["_id"])["auth_providers"] = [{"provider": "google", "subject": "123", "linked_at": None}]
    c.post(f"/api/users/{A2['_id']}/disable", headers=h)
    assert c.post(f"/api/users/{A2['_id']}/enable", headers=h).json()["status"] == "active"


def test_BE29_disable_and_enable_are_idempotent(ctx):
    c, ids, h, db = ctx
    c.post(f"/api/users/{EDITOR_USER['_id']}/disable", headers=h)
    first = stored(db, EDITOR_USER["_id"])["disabled_at"]
    again = c.post(f"/api/users/{EDITOR_USER['_id']}/disable", headers=h)
    assert again.status_code == 200 and stored(db, EDITOR_USER["_id"])["disabled_at"] == first
    assert c.post(f"/api/users/{ADMIN_USER['_id']}/enable", headers=h).json()["status"] == "active"     # ya activo: sin cambios


def test_BE29_disabled_user_cannot_login(ctx):
    c, ids, h, db = ctx
    stored(db, EDITOR_USER["_id"])["auth_providers"][0]["hashed_password"] = user_with_password(EDITOR_USER, "una-clave-larga-123")["auth_providers"][0]["hashed_password"]
    ok = c.post("/api/auth/login", json={"username": EDITOR_USER["email"], "password": "una-clave-larga-123"})
    assert ok.status_code == 200
    c.post(f"/api/users/{EDITOR_USER['_id']}/disable", headers=h)
    assert c.post("/api/auth/login", json={"username": EDITOR_USER["email"], "password": "una-clave-larga-123"}).status_code == 401


def test_BE29_no_physical_delete_route():
    from app.main import app
    from tests.test_BE12_require_access_matrix import _api_routes
    deletes = {r.path for r in _api_routes(app) if "DELETE" in r.methods and r.path.startswith("/api/users")}
    assert deletes == {"/api/users/{user_id}/access/{platform_id}"}            # solo quitar un acceso, nunca borrar un usuario
