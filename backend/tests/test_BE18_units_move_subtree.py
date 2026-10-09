"""
test_BE18_units_move_subtree.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: US-11 · Mover una unidad con su subárbol (R2, T5)
"""
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from tests.conftest import ADMIN_USER, prepare_org, bearer_for, _user, seed_users


@pytest.fixture
def ctx(fake_db):
    ids = prepare_org(fake_db, ADMIN_USER)
    from app.main import app
    c = TestClient(app, raise_server_exceptions=False)
    return c, ids, bearer_for(ADMIN_USER), fake_db


def doc(db, code):
    return next(d for d in db.units.docs if d["code"] == code)


def test_BE18_move_rewrites_subtree_ancestors(ctx):
    c, ids, h, db = ctx
    # nivel 5 bajo AF-TI para tener un subárbol de verdad
    sub = c.post("/api/units", json={"code": "TI-SOP", "name": "Soporte", "level": 5, "parent_id": ids["AF-TI"]}, headers=h).json()
    assert sub["ancestors"] == [ids["DE"], ids["SD-AF"], ids["AF-TI"]]

    r = c.post(f"/api/units/{ids['AF-TI']}/move", json={"parent_id": ids["SD-GP"]}, headers=h)
    assert r.status_code == 200
    assert r.json()["parent_id"] == ids["SD-GP"] and r.json()["ancestors"] == [ids["DE"], ids["SD-GP"]]
    child = c.get(f"/api/units/{sub['_id']}", headers=h).json()
    assert child["ancestors"] == [ids["DE"], ids["SD-GP"], ids["AF-TI"]]                         # el subárbol se reescribió
    assert child["parent_id"] == ids["AF-TI"]                                                      # su padre no cambia
    # nada de lo que no se movió cambió
    assert c.get(f"/api/units/{ids['AF-FIN']}", headers=h).json()["ancestors"] == [ids["DE"], ids["SD-AF"]]


def test_BE18_move_into_own_subtree_rejected(ctx):
    c, ids, h, db = ctx
    sub = c.post("/api/units", json={"code": "TI-SOP", "name": "Soporte", "level": 5, "parent_id": ids["AF-TI"]}, headers=h).json()
    for target in (ids["AF-TI"], sub["_id"]):
        r = c.post(f"/api/units/{ids['AF-TI']}/move", json={"parent_id": target}, headers=h)
        assert r.status_code == 409, target
    assert doc(db, "AF-TI")["parent_id"] == ObjectId(ids["SD-AF"])                                 # no cambió


def test_BE18_move_violating_levels_rejected(ctx):
    c, ids, h, db = ctx
    for code, parent in (("AF-TI", "GAB"), ("AF-TI", "DE"), ("SD-AF", "AF-TI"), ("DE", "SD-AF"), ("AF-TI", "AF-FIN")):
        r = c.post(f"/api/units/{ids[code]}/move", json={"parent_id": ids[parent]}, headers=h)
        assert r.status_code == 409, (code, parent, r.text)


def test_BE18_move_name_collision_rejected(ctx):
    c, ids, h, db = ctx
    c.post("/api/units", json={"code": "GP-FIN", "name": "Finanzas", "level": 4, "parent_id": ids["SD-GP"]}, headers=h)
    r = c.post(f"/api/units/{ids['AF-FIN']}/move", json={"parent_id": ids["SD-GP"]}, headers=h)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "duplicate"
    assert doc(db, "AF-FIN")["parent_id"] == ObjectId(ids["SD-AF"])


def test_BE18_users_keep_unit_id_after_move(ctx):
    c, ids, h, db = ctx
    member = _user("6600000000000000000000c2", "ana@slepllanquihue.cl", "Ana", "TI", [], unit_id=ids["AF-TI"])
    seed_users(db, member)
    assert c.post(f"/api/units/{ids['AF-TI']}/move", json={"parent_id": ids["SD-GP"]}, headers=h).status_code == 200
    stored = next(d for d in db.users.docs if d["email"] == "ana@slepllanquihue.cl")
    assert stored["unit_id"] == ObjectId(ids["AF-TI"])


def test_BE18_move_unknown_or_malformed_ids(ctx):
    c, ids, h, db = ctx
    assert c.post(f"/api/units/{ids['AF-TI']}/move", json={"parent_id": "6600000000000000000000ee"}, headers=h).status_code == 404
    assert c.post(f"/api/units/no-es-id/move", json={"parent_id": ids["SD-GP"]}, headers=h).status_code == 404
    assert c.post(f"/api/units/{ids['AF-TI']}/move", json={"parent_id": "corto"}, headers=h).status_code == 422
    assert c.post(f"/api/units/{ids['AF-TI']}/move", json={"parent_id": {"$ne": None}}, headers=h).status_code == 422
