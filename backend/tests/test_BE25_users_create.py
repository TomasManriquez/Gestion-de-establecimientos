"""
test_BE25_users_create.py
━━━━━━━━━━━━━━━━━━━━━━━━
Tareas: US-18 (alta de funcionario SLEP) y US-19 (alta de usuario de establecimiento)
Cubre R1, R6, R8, C8, C11, C12, C22, T2, T5
"""
import copy
import pytest
from fastapi.testclient import TestClient
from tests.conftest import (ADMIN_USER, DATOS_ADMIN_USER, SAMPLE_ESTABLISHMENT, prepare_org, bearer_for)


@pytest.fixture
def ctx(fake_db):
    ids = prepare_org(fake_db, ADMIN_USER, DATOS_ADMIN_USER)
    fake_db.establishments.seed(copy.deepcopy(SAMPLE_ESTABLISHMENT))          # rbd 7722
    from app.main import app
    return TestClient(app, raise_server_exceptions=True), ids, bearer_for(ADMIN_USER), fake_db


def slep(ids, **kw):
    return {"email": "ana.perez@slepllanquihue.cl", "first_name": "Ana", "last_name": "Pérez",
            "is_slep_staff": True, "unit_id": ids["AF-TI"], **kw}


def school(**kw):
    return {"email": "luis.soto@slepllanquihue.cl", "first_name": "Luis", "last_name": "Soto",
            "is_slep_staff": False, "rbd": "7722", "positions": ["DOCENTE"], **kw}


# ─── US-18 · funcionario SLEP ────────────────────────────────────────────────

def test_BE25_create_slep_user_returns_document(ctx):
    c, ids, h, db = ctx
    r = c.post("/api/users", json=slep(ids, personal_phone="+56912345678", work_extension="4521"), headers=h)
    assert r.status_code == 201
    u = r.json()
    assert u["email"] == "ana.perez@slepllanquihue.cl" and u["status"] == "invited"
    assert u["unit_id"] == ids["AF-TI"] and u["rbd"] is None and u["positions"] == []
    assert u["personal_phone"] == "+56912345678" and u["created_by"] == ADMIN_USER["_id"]
    assert u["invitation"]["sent"] is False and u["invitation"]["last_error"] == "mail_not_configured"
    assert "hashed_password" not in r.text and u["access"] == []
    stored = [d for d in db.users.docs if d["email"] == u["email"]][0]
    assert stored["auth_providers"] == [] and stored["created_at"] is not None                   # sin credencial hasta la invitación


def test_BE25_unit_must_exist_and_be_active(ctx):
    c, ids, h, db = ctx
    r = c.post("/api/users", json=slep(ids, unit_id="6600000000000000000000ee"), headers=h)
    assert r.status_code == 422 and r.json()["detail"][0]["field"] == "unit_id"
    c.post(f"/api/units/{ids['AF-FIN']}/deactivate", headers=h)
    r = c.post("/api/users", json=slep(ids, unit_id=ids["AF-FIN"]), headers=h)
    assert r.status_code == 422 and r.json()["detail"][0]["code"] == "unit_not_found"
    assert not [d for d in db.users.docs if d.get("email") == "ana.perez@slepllanquihue.cl"]


def test_BE25_duplicate_email_case_insensitive_409(ctx):
    c, ids, h, db = ctx
    assert c.post("/api/users", json=slep(ids), headers=h).status_code == 201
    for variant in ("ANA.PEREZ@slepllanquihue.cl", "  Ana.Perez@SLEPLLANQUIHUE.CL "):
        r = c.post("/api/users", json=slep(ids, email=variant), headers=h)
        assert r.status_code == 409
        assert r.json()["detail"]["field"] == "email" and r.json()["detail"]["code"] == "duplicate"
    assert sum(1 for d in db.users.docs if d.get("email") == "ana.perez@slepllanquihue.cl") == 1


def test_BE25_index_duplicate_key_error_is_translated_to_409(ctx, monkeypatch):
    """La garantía final es el índice: si dos altas pasan la pre-verificación a la vez, 409 igual."""
    c, ids, h, db = ctx
    assert c.post("/api/users", json=slep(ids), headers=h).status_code == 201
    from app.users.users_service import users_service
    from tests.fake_mongo import FakeCollection
    def blind(self, filt=None, projection=None):                # la pre-verificación no ve el duplicado
        return FakeCollection.find(self, {"email": "__nadie__"}, projection)
    monkeypatch.setattr(db.users, "find", blind.__get__(db.users))
    r = c.post("/api/users", json=slep(ids), headers=h)
    assert r.status_code == 409


def test_BE25_single_create_delegates_to_create_many(ctx, monkeypatch):
    c, ids, h, db = ctx
    from app.users.users_service import users_service
    calls = []
    original = users_service.create_many
    async def spy(items, actor_id, *a, **kw):
        calls.append(items)
        return await original(items, actor_id, *a, **kw)
    monkeypatch.setattr(users_service, "create_many", spy)
    assert c.post("/api/users", json=slep(ids), headers=h).status_code == 201
    assert len(calls) == 1 and len(calls[0]) == 1 and calls[0][0]["email"] == "ana.perez@slepllanquihue.cl"


@pytest.mark.parametrize("field,value", [
    ("status", "active"), ("access", [{"platform_id": "iam", "role": "admin"}]), ("hashed_password", "x"),
    ("created_by", "6600000000000000000000a0"), ("auth_providers", []), ("_id", "6600000000000000000000a0"), ("role", "admin"),
])
def test_BE25_body_cannot_set_privileged_fields(ctx, field, value):
    c, ids, h, db = ctx
    r = c.post("/api/users", json=slep(ids, **{field: value}), headers=h)
    assert r.status_code == 422
    assert not [d for d in db.users.docs if d.get("email") == "ana.perez@slepllanquihue.cl"]


def test_BE25_only_iam_admin_can_create(ctx):
    c, ids, h, db = ctx
    assert c.post("/api/users", json=slep(ids), headers=bearer_for(DATOS_ADMIN_USER)).status_code == 403
    assert c.post("/api/users", json=slep(ids)).status_code == 401


# ─── US-19 · usuario de establecimiento ──────────────────────────────────────

def test_BE26_create_establishment_user(ctx):
    c, ids, h, db = ctx
    r = c.post("/api/users", json=school(), headers=h)
    assert r.status_code == 201
    u = r.json()
    assert u["rbd"] == "7722" and u["positions"] == ["DOCENTE"] and u["unit_id"] is None and u["is_slep_staff"] is False


def test_BE26_rbd_validated_through_establishments_service(ctx, monkeypatch):
    c, ids, h, db = ctx
    r = c.post("/api/users", json=school(rbd="9999"), headers=h)
    assert r.status_code == 422 and r.json()["detail"][0]["code"] == "rbd_not_found"
    from app.establishments.establishments_service import establishments_service
    asked = []
    original = establishments_service.existing_rbds
    async def spy(rbds):
        asked.append(set(rbds)); return await original(rbds)
    monkeypatch.setattr(establishments_service, "existing_rbds", spy)
    c.post("/api/users", json=school(email="otro@slepllanquihue.cl"), headers=h)
    assert asked == [{"7722"}]                                              # L5: pasa por el service, no por la colección


@pytest.mark.parametrize("positions", [[], ["DOCENTE", "DOCENTE"], ["ENCARGADO_CONVIVENCIA"], ["JEFE"], "DOCENTE"])
def test_BE26_positions_required_and_unique(ctx, positions):
    c, ids, h, db = ctx
    assert c.post("/api/users", json=school(positions=positions), headers=h).status_code == 422


def test_BE26_multiple_positions_allowed(ctx):
    c, ids, h, db = ctx
    r = c.post("/api/users", json=school(positions=["DOCENTE", "PIE_ENCARGADO"]), headers=h)
    assert r.status_code == 201 and r.json()["positions"] == ["DOCENTE", "PIE_ENCARGADO"]


@pytest.mark.parametrize("email", ["luis@gmail.com", "luis@slepllanquihue.gob.cl", "luis@slepllanquihue.cl.evil.com"])
def test_BE26_external_domain_rejected(ctx, email):
    c, ids, h, db = ctx
    assert c.post("/api/users", json=school(email=email), headers=h).status_code == 422


def test_BE26_slep_staff_with_rbd_or_school_with_unit_is_422(ctx):
    c, ids, h, db = ctx
    assert c.post("/api/users", json=slep(ids, rbd="7722"), headers=h).status_code == 422
    assert c.post("/api/users", json=school(unit_id=ids["AF-TI"]), headers=h).status_code == 422
