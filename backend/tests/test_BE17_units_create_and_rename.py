"""
test_BE17_units_create_and_rename.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: US-10 · Crear y renombrar unidades (R2, T1, T3, T5)
"""
import pytest
from fastapi.testclient import TestClient
from tests.conftest import ADMIN_USER, DATOS_ADMIN_USER, prepare_org, bearer_for


@pytest.fixture
def ctx(fake_db):
    ids = prepare_org(fake_db, ADMIN_USER, DATOS_ADMIN_USER)
    from app.main import app
    return TestClient(app, raise_server_exceptions=False), ids, bearer_for(ADMIN_USER)


def test_BE17_create_level4_under_level3(ctx):
    c, ids, h = ctx
    r = c.post("/api/units", json={"code": "af-ser", "name": "Servicios Generales", "level": 4, "parent_id": ids["SD-AF"], "order": 4}, headers=h)
    assert r.status_code == 201
    u = r.json()
    assert u["code"] == "AF-SER" and u["level"] == 4 and u["status"] == "active"
    assert u["ancestors"] == [ids["DE"], ids["SD-AF"]] and u["parent_id"] == ids["SD-AF"]       # calculado por el servidor


def test_BE17_level_rules_enforced(ctx):
    c, ids, h = ctx
    cases = [
        {"code": "X1", "name": "Mal padre", "level": 4, "parent_id": ids["GAB"]},             # nivel 4 bajo nivel 2
        {"code": "X2", "name": "Mal padre", "level": 4, "parent_id": ids["DE"]},              # nivel 4 bajo nivel 1
        {"code": "X3", "name": "Otra raíz", "level": 1},                                       # segundo nivel 1
        {"code": "X4", "name": "Raíz con padre", "level": 1, "parent_id": ids["DE"]},
        {"code": "X5", "name": "Sin padre", "level": 3},
        {"code": "X6", "name": "Nivel 5 bajo 3", "level": 5, "parent_id": ids["SD-AF"]},
    ]
    for body in cases:
        r = c.post("/api/units", json=body, headers=h)
        assert r.status_code == 409, (body, r.text)


def test_BE17_level2_cannot_have_children(ctx):
    c, ids, h = ctx
    r = c.post("/api/units", json={"code": "HIJA", "name": "Hija de Auditoría", "level": 3, "parent_id": ids["AUD"]}, headers=h)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "level2_no_children"


def test_BE17_sibling_name_unique_only_among_siblings(ctx):
    c, ids, h = ctx
    dup = c.post("/api/units", json={"code": "TI-2", "name": "Tecnologías de la Información", "level": 4, "parent_id": ids["SD-AF"]}, headers=h)
    assert dup.status_code == 409 and dup.json()["detail"]["code"] == "duplicate"
    other_parent = c.post("/api/units", json={"code": "TI-3", "name": "Tecnologías de la Información", "level": 4, "parent_id": ids["SD-GP"]}, headers=h)
    assert other_parent.status_code == 201                                                       # otro padre: permitido
    dup_code = c.post("/api/units", json={"code": "AF-TI", "name": "Otra cosa", "level": 4, "parent_id": ids["SD-GP"]}, headers=h)
    assert dup_code.status_code == 409


def test_BE17_code_and_structure_immutable_on_patch(ctx):
    c, ids, h = ctx
    ok = c.patch(f"/api/units/{ids['AF-TI']}", json={"name": "TI y Datos", "order": 7}, headers=h)
    assert ok.status_code == 200 and ok.json()["name"] == "TI y Datos" and ok.json()["code"] == "AF-TI"
    for forbidden in ("code", "level", "parent_id", "ancestors", "status", "head_user_id"):
        r = c.patch(f"/api/units/{ids['AF-TI']}", json={forbidden: "x"}, headers=h)
        assert r.status_code == 422, forbidden
    rename_dup = c.patch(f"/api/units/{ids['AF-TI']}", json={"name": "Finanzas"}, headers=h)
    assert rename_dup.status_code == 409                                                         # hermana con ese nombre


def test_BE17_operator_injection_rejected(ctx):
    c, ids, h = ctx
    for body in ({"code": "OK", "name": {"$ne": None}, "level": 4, "parent_id": ids["SD-AF"]},
                 {"code": {"$gt": ""}, "name": "N", "level": 4, "parent_id": ids["SD-AF"]},
                 {"code": "OK", "name": "N", "level": {"$gt": 0}, "parent_id": ids["SD-AF"]},
                 {"code": "OK", "name": "N", "level": 4, "parent_id": {"$ne": None}}):
        assert c.post("/api/units", json=body, headers=h).status_code == 422
    assert c.patch(f"/api/units/{ids['AF-TI']}", json={"name": {"$ne": None}}, headers=h).status_code == 422


def test_BE17_non_iam_admin_forbidden(ctx):
    c, ids, _ = ctx
    body = {"code": "NUEVA", "name": "Nueva", "level": 4, "parent_id": ids["SD-AF"]}
    assert c.post("/api/units", json=body, headers=bearer_for(DATOS_ADMIN_USER)).status_code == 403
    assert c.patch(f"/api/units/{ids['AF-TI']}", json={"name": "X"}, headers=bearer_for(DATOS_ADMIN_USER)).status_code == 403
    assert c.post("/api/units", json=body).status_code == 401


def test_BE17_code_format_and_max_lengths(ctx):
    c, ids, h = ctx
    for code in ("a", "con espacio", "ñandú", "X" * 13, "--", "A--B"):
        r = c.post("/api/units", json={"code": code, "name": "N", "level": 4, "parent_id": ids["SD-AF"]}, headers=h)
        assert r.status_code == 422, code
    assert c.post("/api/units", json={"code": "OK1", "name": "n" * 121, "level": 4, "parent_id": ids["SD-AF"]}, headers=h).status_code == 422
