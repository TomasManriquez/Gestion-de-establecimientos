"""
test_BE19_units_deactivate.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: US-12 · Desactivar y reactivar una unidad (R2, T5)
"""
import ast
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from tests.conftest import ADMIN_USER, prepare_org, bearer_for, _user, seed_users

APP = Path(__file__).resolve().parents[1] / "app"


@pytest.fixture
def ctx(fake_db):
    ids = prepare_org(fake_db, ADMIN_USER)
    from app.main import app
    return TestClient(app, raise_server_exceptions=False), ids, bearer_for(ADMIN_USER), fake_db


def test_BE19_deactivate_with_active_users_rejected(ctx):
    c, ids, h, db = ctx
    seed_users(db, _user("6600000000000000000000c3", "a@slepllanquihue.cl", "A", "A", [], unit_id=ids["AF-FIN"]),
               _user("6600000000000000000000c4", "b@slepllanquihue.cl", "B", "B", [], unit_id=ids["AF-FIN"]))
    r = c.post(f"/api/units/{ids['AF-FIN']}/deactivate", headers=h)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "has_active_users"
    assert "2" in r.json()["detail"]["message"]
    assert next(d for d in db.units.docs if d["code"] == "AF-FIN")["status"] == "active"


def test_BE19_disabled_users_do_not_block_deactivation(ctx):
    c, ids, h, db = ctx
    seed_users(db, _user("6600000000000000000000c5", "x@slepllanquihue.cl", "X", "X", [], unit_id=ids["AF-FIN"], status="disabled"))
    assert c.post(f"/api/units/{ids['AF-FIN']}/deactivate", headers=h).status_code == 200


def test_BE19_deactivate_with_active_children_rejected(ctx):
    c, ids, h, db = ctx
    r = c.post(f"/api/units/{ids['SD-AF']}/deactivate", headers=h)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "has_active_children"


def test_BE19_deactivate_empty_unit(ctx):
    c, ids, h, db = ctx
    r = c.post(f"/api/units/{ids['AF-FIN']}/deactivate", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "inactive" and r.json()["code"] == "AF-FIN"
    assert ids["AF-FIN"] not in {u["_id"] for u in c.get("/api/units/tree?status=active", headers=h).json()[0]["children"][5]["children"]}


def test_BE19_reactivate_requires_active_parent(ctx):
    c, ids, h, db = ctx
    for code in ("AF-CL", "AF-TI", "AF-FIN"):
        assert c.post(f"/api/units/{ids[code]}/deactivate", headers=h).status_code == 200
    assert c.post(f"/api/units/{ids['SD-AF']}/deactivate", headers=h).status_code == 200
    r = c.post(f"/api/units/{ids['AF-TI']}/activate", headers=h)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "inactive_parent"
    assert c.post(f"/api/units/{ids['SD-AF']}/activate", headers=h).status_code == 200
    assert c.post(f"/api/units/{ids['AF-TI']}/activate", headers=h).status_code == 200


def test_BE19_units_service_does_not_import_users():
    for name in ("units_service.py", "units_entity.py"):
        tree = ast.parse((APP / "units" / name).read_text(encoding="utf-8"))
        mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        assert not any(m.startswith(("app.users", "app.auth")) for m in mods), f"units/{name} importa users o auth"
