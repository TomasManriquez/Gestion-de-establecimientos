"""
test_BE64_access_grants.py
━━━━━━━━━━━━━━━━━━━━━━━━━━
ADR-021, fase 1 · Concesiones por recurso (por persona).
"""
import pytest
from fastapi.testclient import TestClient

from app.access.access_service import access_service
from tests.conftest import (ADMIN_USER, DATOS_ADMIN_USER, EDITOR_USER, VIEWER_USER, _user, bearer_for, prepare_org, run)

URL = "/api/v1/access/grants"
DISABLED = _user("6600000000000000000000b1", "baja@slepllanquihue.cl", "Baja", "Cuenta", [("datos", "viewer")], status="disabled")
VIEWER_ID, EDITOR_ID = str(VIEWER_USER["_id"]), str(EDITOR_USER["_id"])


@pytest.fixture
def ctx(fake_db):
    prepare_org(fake_db, ADMIN_USER, DATOS_ADMIN_USER, EDITOR_USER, VIEWER_USER, DISABLED)
    from app.main import app
    return TestClient(app, raise_server_exceptions=True), bearer_for(ADMIN_USER), fake_db


def _grant(c, h, user_id, resource_id="7722", resource_type="vault"):
    return c.post(URL, json={"resource_type": resource_type, "resource_id": resource_id, "user_id": user_id}, headers=h)


# ── can(): sin concesión no se ve nada ─────────────────────────────────────────────
def test_BE64_can_denies_by_default_and_admin_always_passes(ctx):
    assert run(access_service.can(VIEWER_ID, "vault", "7722")) is False
    assert run(access_service.can(VIEWER_ID, "vault", "7722", is_iam_admin=True)) is True


def test_BE64_can_matrix_exact_wildcard_and_other_person(ctx):
    c, h, db = ctx
    assert _grant(c, h, VIEWER_ID, "7722").status_code == 201
    assert run(access_service.can(VIEWER_ID, "vault", "7722")) is True
    assert run(access_service.can(VIEWER_ID, "vault", "9999")) is False            # otro recurso
    assert run(access_service.can(VIEWER_ID, "portal_resource", "7722")) is False  # otro tipo
    assert run(access_service.can(EDITOR_ID, "vault", "7722")) is False            # otra persona
    assert _grant(c, h, EDITOR_ID, "*").status_code == 201
    assert run(access_service.can(EDITOR_ID, "vault", "9999")) is True             # "*" cubre todos los de su tipo
    assert run(access_service.can(EDITOR_ID, "portal_resource", "9999")) is False


def test_BE64_visible_ids(ctx):
    c, h, db = ctx
    _grant(c, h, VIEWER_ID, "7722")
    _grant(c, h, VIEWER_ID, "8000")
    assert run(access_service.visible_ids(VIEWER_ID, "vault")) == {"7722", "8000"}
    assert run(access_service.visible_ids(EDITOR_ID, "vault")) == set()
    assert run(access_service.visible_ids(VIEWER_ID, "vault", is_iam_admin=True)) is None
    _grant(c, h, VIEWER_ID, "*")
    assert run(access_service.visible_ids(VIEWER_ID, "vault")) is None


# ── API ──────────────────────────────────────────────────────────────────────────
def test_BE64_create_list_and_revoke(ctx):
    c, h, db = ctx
    created = _grant(c, h, VIEWER_ID)
    assert created.status_code == 201
    body = created.json()
    assert body["subject_type"] == "user" and body["subject_id"] == VIEWER_ID and body["granted_by"] == str(ADMIN_USER["_id"])
    assert [g["_id"] for g in c.get(URL, headers=h).json()] == [body["_id"]]
    assert c.get(URL, params={"resource_type": "portal_resource"}, headers=h).json() == []
    assert c.delete(f"{URL}/{body['_id']}", headers=h).status_code == 204
    assert c.get(URL, headers=h).json() == []
    assert run(access_service.can(VIEWER_ID, "vault", "7722")) is False            # revocar surte efecto de inmediato
    assert c.delete(f"{URL}/{body['_id']}", headers=h).status_code == 404
    assert c.delete(f"{URL}/no-es-un-id", headers=h).status_code == 404


def test_BE64_duplicate_unknown_and_inactive_person(ctx):
    c, h, db = ctx
    assert _grant(c, h, VIEWER_ID).status_code == 201
    assert _grant(c, h, VIEWER_ID).status_code == 409
    assert _grant(c, h, "6600000000000000000000ff").status_code == 404
    assert _grant(c, h, str(DISABLED["_id"])).status_code == 422
    assert db.resource_grants.docs.__len__() == 1


@pytest.mark.parametrize("body", [
    {"resource_type": "otro", "resource_id": "7722", "user_id": VIEWER_ID},          # tipo no declarado
    {"resource_type": "vault", "resource_id": "7722", "user_id": "abc"},
    {"resource_type": "vault", "resource_id": {"$ne": None}, "user_id": VIEWER_ID},   # inyección de operador
    {"resource_type": "vault", "resource_id": "a b/..", "user_id": VIEWER_ID},
    {"resource_type": "vault", "resource_id": "7722", "user_id": VIEWER_ID, "subject_type": "unit"},   # extra=forbid
])
def test_BE64_invalid_payloads_are_rejected(ctx, body):
    c, h, db = ctx
    assert c.post(URL, json=body, headers=h).status_code == 422
    assert db.resource_grants.docs == []


def test_BE64_only_iam_admin_manages_grants(ctx):
    c, h, db = ctx
    for user in (DATOS_ADMIN_USER, EDITOR_USER, VIEWER_USER):
        other = bearer_for(user)
        assert c.get(URL, headers=other).status_code == 403
        assert _grant(c, other, VIEWER_ID).status_code == 403
        assert c.delete(f"{URL}/6600000000000000000000ff", headers=other).status_code == 403
    assert c.get(URL).status_code == 401
    assert db.resource_grants.docs == []


# ── auditoría y base ───────────────────────────────────────────────────────────────
def test_BE64_changes_are_audited(ctx):
    c, h, db = ctx
    grant_id = _grant(c, h, VIEWER_ID, "7722").json()["_id"]
    c.delete(f"{URL}/{grant_id}", headers=h)
    entries = [(d["action"], d["target_type"], d["target_id"], d["changes"]["subject_id"]) for d in db.audit_log.docs]
    assert ("resource_grant.create", "resource_grant", grant_id, VIEWER_ID) in entries
    assert ("resource_grant.revoke", "resource_grant", grant_id, VIEWER_ID) in entries


def test_BE64_unique_index_exists(ctx):
    c, h, db = ctx
    assert db.resource_grants._unique, "falta el índice único de resource_grants"
