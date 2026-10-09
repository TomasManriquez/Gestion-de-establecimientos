"""
test_BE20_units_head.py
━━━━━━━━━━━━━━━━━━━━━━━
Tarea: US-13 · Asignar la jefatura de una unidad (R3, T5) — reglas Q7 y Q8
"""
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from tests.conftest import ADMIN_USER, prepare_org, bearer_for, _user, seed_users


@pytest.fixture
def ctx(fake_db):
    ids = prepare_org(fake_db, ADMIN_USER)
    seed_users(fake_db,
               _user("6600000000000000000000d1", "jefa@slepllanquihue.cl", "Julia", "Jefa", [], unit_id=ids["AF-TI"]),
               _user("6600000000000000000000d2", "otra@slepllanquihue.cl", "Olga", "Otra", [], unit_id=ids["AF-FIN"]),
               _user("6600000000000000000000d3", "inactiva@slepllanquihue.cl", "Ines", "Inactiva", [], unit_id=ids["AF-TI"], status="disabled"),
               _user("6600000000000000000000d4", "colegio@slepllanquihue.cl", "Carlos", "Colegio", [], is_slep_staff=False,
                     unit_id=None, rbd="7722", positions=["DOCENTE"]))
    from app.main import app
    return TestClient(app, raise_server_exceptions=False), ids, bearer_for(ADMIN_USER), fake_db


def put_head(c, h, unit_id, user_id):
    return c.put(f"/api/units/{unit_id}/head", json={"user_id": user_id}, headers=h)


def test_BE20_assign_head_to_active_member(ctx):
    c, ids, h, db = ctx
    r = put_head(c, h, ids["AF-TI"], "6600000000000000000000d1")
    assert r.status_code == 200 and r.json()["head_user_id"] == "6600000000000000000000d1"
    assert next(d for d in db.units.docs if d["code"] == "AF-TI")["head_user_id"] == ObjectId("6600000000000000000000d1")


@pytest.mark.parametrize("user_id,code", [
    ("6600000000000000000000d3", "head_inactive"),        # deshabilitado
    ("6600000000000000000000d2", "head_not_member"),      # de otra unidad
    ("6600000000000000000000d4", "head_not_slep_staff"),  # de establecimiento
])
def test_BE20_head_must_be_active_member_of_the_unit(ctx, user_id, code):
    c, ids, h, db = ctx
    r = put_head(c, h, ids["AF-TI"], user_id)
    assert r.status_code == 409 and r.json()["detail"]["code"] == code
    assert next(d for d in db.units.docs if d["code"] == "AF-TI")["head_user_id"] is None


def test_BE20_unknown_user_is_404_and_malformed_is_422(ctx):
    c, ids, h, db = ctx
    assert put_head(c, h, ids["AF-TI"], "6600000000000000000000ee").status_code == 404
    assert put_head(c, h, ids["AF-TI"], "corto").status_code == 422
    assert put_head(c, h, ids["AF-TI"], {"$ne": None}).status_code == 422


def test_BE20_clear_head(ctx):
    c, ids, h, db = ctx
    put_head(c, h, ids["AF-TI"], "6600000000000000000000d1")
    r = put_head(c, h, ids["AF-TI"], None)
    assert r.status_code == 200 and r.json()["head_user_id"] is None


def test_BE20_disabling_head_clears_head_user_id(ctx):
    """Q8: desactivar a quien es jefatura es el caso normal; no se bloquea, se libera el cargo."""
    c, ids, h, db = ctx
    put_head(c, h, ids["AF-TI"], "6600000000000000000000d1")
    r = c.post("/api/users/6600000000000000000000d1/disable", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "disabled"
    assert next(d for d in db.units.docs if d["code"] == "AF-TI")["head_user_id"] is None


def test_BE20_only_iam_admin_can_set_head(ctx):
    c, ids, h, db = ctx
    from tests.conftest import DATOS_ADMIN_USER
    seed_users(db, DATOS_ADMIN_USER)
    assert put_head(c, bearer_for(DATOS_ADMIN_USER), ids["AF-TI"], "6600000000000000000000d1").status_code == 403
