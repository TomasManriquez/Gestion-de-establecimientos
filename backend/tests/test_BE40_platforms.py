"""
test_BE40_platforms.py
━━━━━━━━━━━━━━━━━━━━━━
Tarea: US-33 · Registro de plataformas (R11, C12, C14)
"""
import pytest
from fastapi.testclient import TestClient
from app.platforms.platforms_service import platforms_service
from tests.conftest import ADMIN_USER, DATOS_ADMIN_USER, prepare_org, bearer_for


@pytest.fixture
def ctx(fake_db):
    prepare_org(fake_db, ADMIN_USER, DATOS_ADMIN_USER)
    from app.main import app
    return TestClient(app, raise_server_exceptions=True), bearer_for(ADMIN_USER), fake_db


@pytest.mark.asyncio
async def test_BE40_bootstrap_seeds_three_platforms(fake_db):
    await platforms_service.ensure_bootstrap_platforms()
    await platforms_service.ensure_bootstrap_platforms()                  # idempotente
    docs = {d["_id"]: d for d in fake_db.platforms.docs}
    assert set(docs) == {"iam", "datos", "selloverde"}
    assert docs["iam"]["roles"] == ["admin"]                              # iam solo tiene admin (C12)
    assert docs["datos"]["roles"] == docs["selloverde"]["roles"] == ["admin", "editor", "viewer"]
    assert all(d["status"] == "active" for d in docs.values())


@pytest.mark.asyncio
async def test_BE40_bootstrap_skips_when_not_empty(fake_db):
    await fake_db.platforms.insert_one({"_id": "otra", "name": "Otra", "roles": ["admin"], "status": "active", "base_url": ""})
    await platforms_service.ensure_bootstrap_platforms()
    assert await fake_db.platforms.count_documents({}) == 1


def test_BE40_list_platforms(ctx):
    c, h, db = ctx
    r = c.get("/api/platforms", headers=h)
    assert r.status_code == 200
    assert [p["_id"] for p in r.json()] == ["datos", "iam", "selloverde"]          # _id es el slug estable
    assert {"_id", "name", "base_url", "roles", "status"} == set(r.json()[0])


def test_BE40_patch_only_name_and_status(ctx):
    c, h, db = ctx
    ok = c.patch("/api/platforms/selloverde", json={"name": "Sello Verde Escolar", "status": "inactive"}, headers=h)
    assert ok.status_code == 200 and ok.json()["name"] == "Sello Verde Escolar" and ok.json()["status"] == "inactive"
    assert ok.json()["roles"] == ["admin", "editor", "viewer"]
    for forbidden in ({"roles": ["admin"]}, {"_id": "otro"}, {"base_url": "https://evil.example"}):
        assert c.patch("/api/platforms/selloverde", json=forbidden, headers=h).status_code == 422
    assert c.patch("/api/platforms/selloverde", json={"status": "borrada"}, headers=h).status_code == 422
    assert c.patch("/api/platforms/selloverde", json={"name": {"$ne": None}}, headers=h).status_code == 422
    assert c.patch("/api/platforms/no-existe", json={"name": "X"}, headers=h).status_code == 404


def test_BE40_only_iam_admin_can_write(ctx):
    c, h, db = ctx
    other = bearer_for(DATOS_ADMIN_USER)
    assert c.get("/api/platforms", headers=other).status_code == 403
    assert c.patch("/api/platforms/datos", json={"name": "X"}, headers=other).status_code == 403
    assert c.get("/api/platforms").status_code == 401
