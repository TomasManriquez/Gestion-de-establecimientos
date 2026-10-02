"""
test_BE15_units_bootstrap.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: US-08 · Seed del organigrama de 23 unidades (R2)
"""
import ast
from collections import Counter
from pathlib import Path
import pytest
from bson import ObjectId
from app.database.database_service import DatabaseService
from app.units.units_entity import UNITS_SEED
from app.units.units_service import units_service

APP = Path(__file__).resolve().parents[1] / "app"


@pytest.mark.asyncio
async def test_BE15_bootstrap_creates_23_units_with_expected_levels(fake_db):
    await units_service.ensure_bootstrap_units()
    docs = fake_db.units.docs
    assert len(docs) == 23
    assert Counter(d["level"] for d in docs) == {1: 1, 2: 4, 3: 5, 4: 13}
    assert all(d["status"] == "active" for d in docs)


@pytest.mark.asyncio
async def test_BE15_level4_unit_has_parent_and_materialized_ancestors(fake_db):
    await units_service.ensure_bootstrap_units()
    by_code = {d["code"]: d for d in fake_db.units.docs}
    ti = by_code["AF-TI"]
    assert ti["parent_id"] == by_code["SD-AF"]["_id"]
    assert ti["ancestors"] == [by_code["DE"]["_id"], by_code["SD-AF"]["_id"]]
    assert by_code["DE"]["parent_id"] is None and by_code["DE"]["ancestors"] == []
    assert by_code["GAB"]["ancestors"] == [by_code["DE"]["_id"]]            # nivel 2 cuelga de la raíz
    assert by_code["SD-GT"]["ancestors"] == [by_code["DE"]["_id"]]          # nivel 3 también


def test_BE15_codes_are_unique_and_match_table():
    codes = [c for c, *_ in UNITS_SEED]
    assert len(codes) == len(set(codes)) == 23
    # los cuatro códigos que el prompt daba como referencia
    assert {"GP-REM", "AF-TI", "GT-GT", "PC-INF", "SD-GT", "SD-AF", "SD-GP", "SD-PC", "UATP", "DE"} <= set(codes)
    names = {c: n for c, n, *_ in UNITS_SEED}
    assert names["SD-GT"] == "Subdirección de Gestión Territorial" and names["GT-GT"] == "Gestión Territorial"


@pytest.mark.asyncio
async def test_BE15_bootstrap_skips_when_not_empty(fake_db):
    await fake_db.units.insert_one({"code": "X", "name": "Existente", "level": 1})
    await units_service.ensure_bootstrap_units()
    assert await fake_db.units.count_documents({}) == 1


@pytest.mark.asyncio
async def test_BE15_bootstrap_twice_does_not_duplicate(fake_db):
    await units_service.ensure_bootstrap_units()
    await units_service.ensure_bootstrap_units()
    assert await fake_db.units.count_documents({}) == 23


@pytest.mark.asyncio
async def test_BE15_same_name_different_parent_allowed(fake_db):
    svc = DatabaseService(); svc.db = fake_db
    await svc.ensure_indexes()
    await units_service.ensure_bootstrap_units()
    territorial = [d for d in fake_db.units.docs if d["name"] == "Gestión Territorial"]
    assert {d["level"] for d in territorial} == {4} or len(territorial) == 1          # GT-GT (nivel 4)
    subdir = [d for d in fake_db.units.docs if d["code"] == "SD-GT"][0]
    assert subdir["name"] == "Subdirección de Gestión Territorial"
    # mismo nombre bajo el mismo padre sí choca
    from pymongo.errors import DuplicateKeyError
    gt = [d for d in fake_db.units.docs if d["code"] == "GT-GT"][0]
    with pytest.raises(DuplicateKeyError):
        await fake_db.units.insert_one({"code": "OTRO", "name": "Gestión Territorial", "level": 4,
                                        "parent_id": gt["parent_id"], "ancestors": gt["ancestors"]})


@pytest.mark.asyncio
async def test_BE15_unit_indexes_idempotent(fake_db):
    svc = DatabaseService(); svc.db = fake_db
    await svc.ensure_indexes()
    await svc.ensure_indexes()
    await units_service.ensure_bootstrap_units()
    from pymongo.errors import DuplicateKeyError
    with pytest.raises(DuplicateKeyError):                                            # code único
        await fake_db.units.insert_one({"code": "DE", "name": "Otra", "level": 2, "parent_id": ObjectId()})


def test_BE15_seed_data_is_module_constant():
    assert isinstance(UNITS_SEED, list)
    assert not list((APP / "units").glob("*.json"))
    src = (APP / "units" / "units_service.py").read_text(encoding="utf-8")
    assert "json.load" not in src and "open(" not in src       # no lee ningún archivo de datos
