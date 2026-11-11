"""
test_BE67_unit_grants.py
━━━━━━━━━━━━━━━━━━━━━━━━
ADR-021, fase 4 · Concesiones por unidad (y subunidades).
"""
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from tests.conftest import (ADMIN_USER, DATOS_ADMIN_USER, EDITOR_USER, SAMPLE_ESTABLISHMENT, VIEWER_USER, bearer_for,
                            prepare_org, run)

URL = "/api/v1/access/grants"
RBD = SAMPLE_ESTABLISHMENT["rbd"]
VAULT = f"/api/v1/establishments/{RBD}/vault"


@pytest.fixture
def ctx(fake_db):
    units = prepare_org(fake_db, ADMIN_USER, DATOS_ADMIN_USER, EDITOR_USER, VIEWER_USER)
    run(fake_db.establishments.insert_one(dict(SAMPLE_ESTABLISHMENT)))
    for d in fake_db.users.docs:                       # viewer en Compras y Logística (hijo de SD-AF); editor en otra rama
        if str(d["_id"]) == str(VIEWER_USER["_id"]):
            d["unit_id"] = ObjectId(units["AF-CL"])
        if str(d["_id"]) == str(EDITOR_USER["_id"]):
            d["unit_id"] = ObjectId(units["GP-REM"])
    from app.main import app
    return TestClient(app, raise_server_exceptions=True), bearer_for(ADMIN_USER), fake_db, units


def _grant(c, h, unit_id, include=False, resource_type="vault", resource_id=RBD):
    return c.post(URL, json={"resource_type": resource_type, "resource_id": resource_id, "unit_id": unit_id,
                             "include_subunits": include}, headers=h)


def test_BE67_unit_grant_with_subunits_covers_descendants_only(ctx):
    c, admin, db, units = ctx
    viewer, editor = bearer_for(VIEWER_USER), bearer_for(EDITOR_USER)
    assert c.get(VAULT, headers=viewer).status_code == 403
    assert _grant(c, admin, units["SD-AF"], include=True).status_code == 201
    assert c.get(VAULT, headers=viewer).status_code == 200          # AF-CL cuelga de SD-AF
    assert c.get(VAULT, headers=editor).status_code == 403          # GP-REM es de otra rama


def test_BE67_unit_grant_without_subunits_covers_only_that_unit(ctx):
    c, admin, db, units = ctx
    viewer = bearer_for(VIEWER_USER)
    assert _grant(c, admin, units["SD-AF"], include=False).status_code == 201
    assert c.get(VAULT, headers=viewer).status_code == 403          # la subunidad no hereda sin include_subunits
    assert _grant(c, admin, units["AF-CL"], include=False).status_code == 201
    assert c.get(VAULT, headers=viewer).status_code == 200          # su propia unidad sí


def test_BE67_user_without_unit_is_never_covered(ctx):
    c, admin, db, units = ctx
    for d in db.users.docs:
        if str(d["_id"]) == str(VIEWER_USER["_id"]):
            d["unit_id"] = None
    assert _grant(c, admin, units["DE"], include=True, resource_id="*").status_code == 201
    assert c.get(VAULT, headers=bearer_for(VIEWER_USER)).status_code == 403


def test_BE67_unit_grant_opens_restricted_portal_resources(ctx):
    c, admin, db, units = ctx
    topic = c.post("/api/v1/portal/topics", json={"name": "Finanzas"}, headers=admin).json()["_id"]
    rid = c.post("/api/v1/portal/resources", json={"title": "Sueldos", "url": "https://x.cl/s", "topic_id": topic,
                                                   "data_categories": ["students"]}, headers=admin).json()["_id"]
    viewer = bearer_for(VIEWER_USER)
    assert c.get(f"/api/v1/portal/resources/{rid}", headers=viewer).status_code == 404
    assert _grant(c, admin, units["SD-AF"], include=True, resource_type="portal_resource", resource_id=rid).status_code == 201
    assert c.get(f"/api/v1/portal/resources/{rid}", headers=viewer).status_code == 200
    assert rid in {r["_id"] for r in c.get("/api/v1/portal/resources", headers=viewer).json()}


def test_BE67_payload_rules_and_duplicates(ctx):
    c, admin, db, units = ctx
    uid = str(VIEWER_USER["_id"])
    base = {"resource_type": "vault", "resource_id": RBD}
    assert c.post(URL, json={**base, "user_id": uid, "unit_id": units["SD-AF"]}, headers=admin).status_code == 422   # ambas
    assert c.post(URL, json=base, headers=admin).status_code == 422                                                  # ninguna
    assert c.post(URL, json={**base, "user_id": uid, "include_subunits": True}, headers=admin).status_code == 422
    assert _grant(c, admin, "a" * 24).status_code == 404
    assert _grant(c, admin, units["SD-AF"]).status_code == 201
    assert _grant(c, admin, units["SD-AF"]).status_code == 409
    for d in db.units.docs:
        if str(d["_id"]) == units["AUD"]:
            d["status"] = "inactive"
    assert _grant(c, admin, units["AUD"]).status_code == 422


def test_BE67_unit_grant_is_listed_audited_and_revocable(ctx):
    c, admin, db, units = ctx
    g = _grant(c, admin, units["SD-AF"], include=True).json()
    assert g["subject_type"] == "unit" and g["subject_id"] == units["SD-AF"] and g["include_subunits"] is True
    assert c.delete(f"{URL}/{g['_id']}", headers=admin).status_code == 204
    assert c.get(VAULT, headers=bearer_for(VIEWER_USER)).status_code == 403
    created = [d for d in db.audit_log.docs if d["action"] == "resource_grant.create"][0]
    assert created["changes"]["subject_type"] == "unit" and created["changes"]["include_subunits"] is True
