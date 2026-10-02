"""
test_BE10_admin_bootstrap_and_migration.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: US-03 · Migrar el admin sembrado al modelo nuevo (C2, C6, C12, T9)

Verifica que:
  - el admin legado {username, hashed_password, role} se migra en el mismo _id y conserva su hash
  - con la base vacía se crea con ADMIN_PASSWORD, must_change_password y la unidad AF-TI
  - es idempotente y tolera la carrera de dos workers
  - el índice único de `email` es parcial (los documentos legados sin correo no chocan)
  - seed_service ya no siembra usuarios y `database` no importa módulos de dominio
"""
import ast
from pathlib import Path
import pytest
from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from app.auth.auth_service import auth_service
from app.config import settings
from app.database.database_service import DatabaseService
from app.units.units_service import units_service
from app.users.users_service import users_service
from tests.conftest import hashed

APP = Path(__file__).resolve().parents[1] / "app"
EMAIL = "admin@slepllanquihue.cl"
OLD_PASSWORD = "la-clave-de-siempre"


def legacy_admin():
    return {"username": "admin", "hashed_password": hashed(OLD_PASSWORD),
            "full_name": "Administrador SLEP", "role": "admin"}


async def bootstrap(make_hash=lambda: hashed("ADMIN-PASSWORD-DE-PRUEBA")):
    await units_service.ensure_bootstrap_units()
    await users_service.ensure_bootstrap_admin(EMAIL, make_hash)


@pytest.mark.asyncio
async def test_BE10_legacy_admin_is_migrated_in_place(fake_db):
    legacy_id = (await fake_db.users.insert_one(legacy_admin())).inserted_id
    await bootstrap()

    assert await fake_db.users.count_documents({}) == 1
    doc = await fake_db.users.find_one({"_id": legacy_id})
    assert doc["email"] == EMAIL and doc["status"] == "active"
    assert doc["is_slep_staff"] is True and doc["unit_id"] is not None and doc["rbd"] is None
    assert {(a["platform_id"], a["role"]) for a in doc["access"]} == {("iam", "admin"), ("datos", "admin")}
    local = [p for p in doc["auth_providers"] if p["provider"] == "local"]
    assert len(local) == 1
    assert auth_service.verify_password(OLD_PASSWORD, local[0]["hashed_password"])     # conserva el hash original
    # campos legados intactos: volver al código anterior sigue funcionando (rollback)
    assert doc["username"] == "admin" and doc["role"] == "admin" and doc["hashed_password"]


@pytest.mark.asyncio
async def test_BE10_migrated_admin_can_login_with_old_password(fake_db):
    await fake_db.users.insert_one(legacy_admin())
    await bootstrap()
    assert await auth_service.authenticate_user(EMAIL, OLD_PASSWORD) is not None
    assert await auth_service.authenticate_user("admin", OLD_PASSWORD) is not None          # username legado
    assert await auth_service.authenticate_user(EMAIL, "otra-clave") is None


@pytest.mark.asyncio
async def test_BE10_bootstrap_is_idempotent(fake_db):
    await fake_db.users.insert_one(legacy_admin())
    await bootstrap()
    before = await fake_db.users.find_one({"email": EMAIL})
    await bootstrap()
    after = await fake_db.users.find_one({"email": EMAIL})
    assert await fake_db.users.count_documents({}) == 1
    assert before == after


@pytest.mark.asyncio
async def test_BE10_empty_db_creates_admin_after_units(fake_db):
    await bootstrap()
    doc = await fake_db.users.find_one({"email": EMAIL})
    unit = await fake_db.units.find_one({"_id": doc["unit_id"]})
    assert unit["code"] == "AF-TI"
    assert doc["status"] == "active" and doc["is_slep_staff"] is True
    local = doc["auth_providers"][0]
    assert local["must_change_password"] is True
    assert auth_service.verify_password("ADMIN-PASSWORD-DE-PRUEBA", local["hashed_password"])
    assert {(a["platform_id"], a["role"]) for a in doc["access"]} == {("iam", "admin"), ("datos", "admin")}


@pytest.mark.asyncio
async def test_BE10_bootstrap_does_not_hash_when_admin_already_exists(fake_db):
    await bootstrap()
    calls = []
    await users_service.ensure_bootstrap_admin(EMAIL, lambda: calls.append(1) or "x")
    assert calls == []                                    # bcrypt es caro: no se calcula si no hace falta


@pytest.mark.asyncio
async def test_BE10_bootstrap_requires_units_first(fake_db):
    with pytest.raises(RuntimeError, match="unidades"):
        await users_service.ensure_bootstrap_admin(EMAIL, lambda: "hash")


@pytest.mark.asyncio
async def test_BE10_bootstrap_tolerates_duplicate_key_race(fake_db, monkeypatch):
    """Dos workers de Gunicorn: el segundo recibe DuplicateKeyError y el arranque sigue."""
    await units_service.ensure_bootstrap_units()

    async def lost_race(doc):
        raise DuplicateKeyError("E11000 duplicate key: email")
    monkeypatch.setattr(fake_db.users, "insert_one", lost_race)
    await users_service.ensure_bootstrap_admin(EMAIL, lambda: hashed("x" * 20))      # no lanza


@pytest.mark.asyncio
async def test_BE10_email_index_is_partial_unique_and_idempotent(fake_db):
    svc = DatabaseService()
    svc.db = fake_db
    await svc.ensure_indexes()
    await svc.ensure_indexes()                                                        # idempotente
    # dos documentos legados sin correo no chocan...
    await fake_db.users.insert_one({"username": "admin"})
    await fake_db.users.insert_one({"username": "otro"})
    # ...pero dos con el mismo correo sí
    await fake_db.users.insert_one({"email": "a@slepllanquihue.cl"})
    with pytest.raises(DuplicateKeyError):
        await fake_db.users.insert_one({"email": "a@slepllanquihue.cl"})


def test_BE10_seed_service_no_longer_seeds_admin():
    from app.database import seed_service
    assert not hasattr(seed_service, "_seed_admin_user")
    for name in ("seed_service.py", "database_service.py"):
        tree = ast.parse((APP / "database" / name).read_text(encoding="utf-8"))
        mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        assert not any(m.startswith(("app.users", "app.units", "app.auth", "app.platforms")) for m in mods), \
            f"database/{name} no debe importar módulos de dominio"


@pytest.mark.asyncio
async def test_BE10_no_hashed_password_in_auth_me_json(fake_db):
    from fastapi.testclient import TestClient
    from app.main import app
    from tests.conftest import bearer_for
    await fake_db.users.insert_one(legacy_admin())
    await bootstrap()
    doc = await fake_db.users.find_one({"email": EMAIL})
    res = TestClient(app).get("/api/auth/me", headers=bearer_for({"_id": doc["_id"]}))
    assert res.status_code == 200
    assert "hashed_password" not in res.text and "$2b$" not in res.text
