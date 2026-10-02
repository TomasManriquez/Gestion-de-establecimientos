"""
test_BE30_users_activity.py
━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: US-23 · Última actividad (R5)
"""
from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from tests.conftest import ADMIN_USER, seed_users, bearer_for, user_with_password
from app.users.users_service import ACTIVITY_THROTTLE, _utcnow, users_service

PASSWORD = "una-clave-larga-de-prueba"


def stored(db):
    return db.users.docs[0]


def test_BE30_login_updates_last_login_at(fake_db):
    seed_users(fake_db, user_with_password(ADMIN_USER, PASSWORD))
    from app.main import app
    assert stored(fake_db)["last_login_at"] is None
    TestClient(app).post("/api/auth/login", json={"username": ADMIN_USER["email"], "password": PASSWORD})
    assert stored(fake_db)["last_login_at"] is not None


def test_BE30_activity_write_is_throttled(fake_db):
    seed_users(fake_db, ADMIN_USER)
    from app.main import app
    c, h = TestClient(app), bearer_for(ADMIN_USER)
    c.get("/api/auth/me", headers=h)
    first = stored(fake_db)["last_activity_at"]
    assert first is not None
    writes = fake_db.users.calls.count("update_one")
    for _ in range(5):
        c.get("/api/auth/me", headers=h)                                      # dentro de la ventana: sin escrituras
    assert fake_db.users.calls.count("update_one") == writes and stored(fake_db)["last_activity_at"] == first
    stored(fake_db)["last_activity_at"] = _utcnow() - ACTIVITY_THROTTLE - timedelta(seconds=1)   # venció la ventana
    c.get("/api/auth/me", headers=h)
    assert stored(fake_db)["last_activity_at"] > first - timedelta(seconds=1)
    assert fake_db.users.calls.count("update_one") == writes + 1


@pytest.mark.asyncio
async def test_BE30_activity_update_is_conditional(fake_db):
    """Dos workers leyeron el mismo documento: solo uno escribe (el filtro exige la ventana vencida)."""
    seed_users(fake_db, ADMIN_USER)
    snapshot = dict(stored(fake_db), _id=str(stored(fake_db)["_id"]))
    assert await users_service.touch_activity(snapshot) is True
    assert await users_service.touch_activity(snapshot) is False              # el otro worker ya escribió
    assert fake_db.users.calls.count("update_one") == 2


@pytest.mark.asyncio
async def test_BE30_activity_failure_does_not_fail_request(fake_db, monkeypatch):
    seed_users(fake_db, ADMIN_USER)
    async def boom(*a, **k):
        raise RuntimeError("Mongo caído")
    monkeypatch.setattr(fake_db.users, "update_one", boom)
    snapshot = dict(stored(fake_db), _id=str(stored(fake_db)["_id"]))
    assert await users_service.touch_activity(snapshot) is False              # se registra y sigue


def test_BE30_activity_does_not_touch_updated_at(fake_db):
    seed_users(fake_db, ADMIN_USER)
    from app.main import app
    TestClient(app).get("/api/auth/me", headers=bearer_for(ADMIN_USER))
    assert stored(fake_db)["last_activity_at"] is not None
    assert stored(fake_db)["updated_at"] is None and stored(fake_db)["updated_by"] is None
