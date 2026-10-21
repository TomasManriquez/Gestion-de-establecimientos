"""
test_BE58_licenses_retired.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: N15 · Retiro del campo `licenses` (credenciales de plataformas externas en claro)

Verifica que:
  - los modelos de establecimiento ya no declaran `licenses`
  - un documento antiguo que aún lo tenga en Mongo no lo devuelve el detalle (ni redactado ni en claro)
  - un PUT que lo envíe lo ignora: no se guarda y no cambia nada más
  - el seed no lo escribe
  - `scripts/retire_licenses.py` cuenta sin modificar y, con --apply, lo borra sin imprimir credenciales
"""
import asyncio
import copy
import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.establishments.establishments_entity import Establishment, EstablishmentUpdate
from tests.conftest import EDITOR_USER, SAMPLE_ESTABLISHMENT, VIEWER_USER, bearer_for, seed_users

STALE = [{"name": "SIGE", "email": "usuario@liceo.cl", "password": "clave-antigua-no-debe-salir"}]


@pytest.fixture
def stale_db(fake_db):
    doc = copy.deepcopy(SAMPLE_ESTABLISHMENT)
    doc["licenses"] = copy.deepcopy(STALE)
    fake_db.establishments.seed(doc)
    seed_users(fake_db, VIEWER_USER, EDITOR_USER)
    return fake_db


def test_BE58_models_do_not_declare_licenses():
    assert "licenses" not in Establishment.model_fields
    assert "licenses" not in EstablishmentUpdate.model_fields


@pytest.mark.parametrize("user", [VIEWER_USER, EDITOR_USER])
def test_BE58_stale_licenses_in_mongo_are_never_served(stale_db, user):
    from app.main import app
    r = TestClient(app).get("/api/establishments/7722", headers=bearer_for(user))
    assert r.status_code == 200
    assert "licenses" not in r.json()
    assert "clave-antigua" not in r.text and "usuario@liceo.cl" not in r.text


def test_BE58_put_with_licenses_ignores_them(stale_db):
    from app.main import app
    body = {"name": "NUEVO NOMBRE", "licenses": [{"name": "X", "email": "x@x.cl", "password": "otra-clave-nueva"}]}
    r = TestClient(app).put("/api/establishments/7722", json=body, headers=bearer_for(EDITOR_USER))
    assert r.status_code == 200 and r.json()["name"] == "NUEVO NOMBRE" and "licenses" not in r.json()
    assert "otra-clave-nueva" not in str(stale_db.establishments.docs[0])


def test_BE58_seed_does_not_write_licenses():
    src = (Path(__file__).resolve().parents[1] / "app" / "database" / "seed_service.py").read_text(encoding="utf-8")
    assert "licenses" not in src


def _load_script():
    path = Path(__file__).resolve().parents[1] / "scripts" / "retire_licenses.py"
    spec = importlib.util.spec_from_file_location("retire_licenses", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeClient:
    def __init__(self, db):
        self._db = db

    def __getitem__(self, name):
        return self._db


def test_BE58_retire_script_dry_run_then_apply(stale_db, capsys):
    script = _load_script()
    with patch.object(script, "AsyncIOMotorClient", lambda url: _FakeClient(stale_db)):
        asyncio.run(script.main(apply=False))
        assert "licenses" in stale_db.establishments.docs[0]                  # simulación: no tocó nada
        dry = capsys.readouterr().out
        assert "con `licenses`: 1" in dry and "no se modificó nada" in dry
        asyncio.run(script.main(apply=True))
        assert "licenses" not in stale_db.establishments.docs[0]
        asyncio.run(script.main(apply=True))                                  # idempotente
    out = dry + capsys.readouterr().out
    assert "clave-antigua" not in out and "usuario@liceo.cl" not in out
    assert "Rótelas" in out or "ATENCIÓN" in out
