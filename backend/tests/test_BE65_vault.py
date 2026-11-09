"""
test_BE65_vault.py
━━━━━━━━━━━━━━━━━━
ADR-021, fase 2 · Bóveda de credenciales por establecimiento.
"""
import json

import pytest
from fastapi.testclient import TestClient

from app.config import ConfigError, Settings
from tests.conftest import (ADMIN_USER, DATOS_ADMIN_USER, EDITOR_USER, SAMPLE_ESTABLISHMENT, VIEWER_USER, bearer_for,
                            prepare_org, run)

RBD = SAMPLE_ESTABLISHMENT["rbd"]
URL = f"/api/v1/establishments/{RBD}/vault"
SECRET = "S3creto-SIGE-¡único!"
VIEWER_ID, EDITOR_ID = str(VIEWER_USER["_id"]), str(EDITOR_USER["_id"])


@pytest.fixture
def ctx(fake_db):
    prepare_org(fake_db, ADMIN_USER, DATOS_ADMIN_USER, EDITOR_USER, VIEWER_USER)
    run(fake_db.establishments.insert_one(dict(SAMPLE_ESTABLISHMENT)))
    from app.main import app
    return TestClient(app, raise_server_exceptions=True), bearer_for(ADMIN_USER), fake_db


def _grant(c, admin_h, user_id, resource_id=RBD):
    r = c.post("/api/v1/access/grants", json={"resource_type": "vault", "resource_id": resource_id, "user_id": user_id},
               headers=admin_h)
    assert r.status_code == 201


def _create(c, h, **extra):
    body = {"name": "SIGE", "username": "director", "password": SECRET, "url": "https://sige.mineduc.cl", **extra}
    return c.post(URL, json=body, headers=h)


# ── acceso: solo concesión o iam/admin; el rol de `datos` no abre nada ─────────────────────
def test_BE65_without_grant_every_verb_is_403_even_for_datos_admin(ctx):
    c, h, db = ctx
    cred_id = _create(c, h).json()["_id"]
    for user in (DATOS_ADMIN_USER, EDITOR_USER, VIEWER_USER):
        other = bearer_for(user)
        assert c.get(URL, headers=other).status_code == 403
        assert _create(c, other).status_code == 403
        assert c.put(f"{URL}/{cred_id}", json={"name": "x"}, headers=other).status_code == 403
        assert c.delete(f"{URL}/{cred_id}", headers=other).status_code == 403
        assert c.post(f"{URL}/{cred_id}/reveal", headers=other).status_code == 403
    assert c.get(URL).status_code == 401
    assert len(db.vault_credentials.docs) == 1


def test_BE65_grant_opens_only_that_establishment_and_star_opens_all(ctx):
    c, h, db = ctx
    viewer = bearer_for(VIEWER_USER)
    _grant(c, h, VIEWER_ID, "9999")
    assert c.get(URL, headers=viewer).status_code == 403             # concesión de otro establecimiento
    _grant(c, h, VIEWER_ID, RBD)
    assert c.get(URL, headers=viewer).status_code == 200
    _grant(c, h, EDITOR_ID, "*")
    assert c.get(URL, headers=bearer_for(EDITOR_USER)).status_code == 200


def test_BE65_unknown_establishment_is_404(ctx):
    c, h, db = ctx
    assert c.get("/api/v1/establishments/0000/vault", headers=h).status_code == 404


# ── la contraseña: cifrada en reposo y solo sale por reveal ────────────────────────────────
def test_BE65_password_is_encrypted_at_rest_and_never_in_normal_responses(ctx):
    c, h, db = ctx
    created = _create(c, h)
    assert created.status_code == 201
    body = created.json()
    assert body["has_password"] is True and "password" not in body and "password_enc" not in body
    stored = db.vault_credentials.docs[0]
    assert SECRET not in json.dumps(stored, default=str) and stored["password_enc"]
    for resp in (c.get(URL, headers=h), c.put(f"{URL}/{body['_id']}", json={"name": "SIGE 2"}, headers=h)):
        assert resp.status_code == 200
        assert SECRET not in resp.text and "password" not in resp.text.replace("has_password", "")


def test_BE65_reveal_returns_password_with_no_store_and_is_audited(ctx):
    c, h, db = ctx
    cred_id = _create(c, h).json()["_id"]
    r = c.post(f"{URL}/{cred_id}/reveal", headers=h)
    assert r.status_code == 200 and r.json() == {"password": SECRET}
    assert r.headers["cache-control"] == "no-store"
    reveals = [d for d in db.audit_log.docs if d["action"] == "vault.reveal"]
    assert len(reveals) == 1 and reveals[0]["target_id"] == cred_id
    assert reveals[0]["changes"] == {"rbd": RBD, "name": "SIGE"}
    assert c.post(f"{URL}/6600000000000000000000ff/reveal", headers=h).status_code == 404


def test_BE65_reveal_fails_closed_when_audit_cannot_be_written(ctx, monkeypatch):
    c, h, db = ctx
    cred_id = _create(c, h).json()["_id"]

    async def broken(*a, **k):
        return False
    monkeypatch.setattr("app.vault.vault_service.audit_service.record", broken)
    r = c.post(f"{URL}/{cred_id}/reveal", headers=h)
    assert r.status_code == 503 and SECRET not in r.text


def test_BE65_reveal_is_rate_limited_per_person(ctx, monkeypatch):
    c, h, db = ctx
    cred_id = _create(c, h).json()["_id"]
    monkeypatch.setattr("app.vault.vault_controller.REVEAL_LIMIT", 2)
    _grant(c, h, VIEWER_ID)
    viewer = bearer_for(VIEWER_USER)
    assert [c.post(f"{URL}/{cred_id}/reveal", headers=viewer).status_code for _ in range(3)] == [200, 200, 429]
    assert "Retry-After" in c.post(f"{URL}/{cred_id}/reveal", headers=viewer).headers
    assert c.post(f"{URL}/{cred_id}/reveal", headers=h).status_code == 200     # el tope es por persona, no global


# ── cambios y log ─────────────────────────────────────────────────────────────────────────
def test_BE65_update_keeps_or_replaces_password_and_logs_only_that_it_changed(ctx):
    c, h, db = ctx
    cred_id = _create(c, h).json()["_id"]
    assert c.put(f"{URL}/{cred_id}", json={"name": "SIGE nuevo", "username": None}, headers=h).status_code == 200
    stored = db.vault_credentials.docs[0]
    assert stored["name"] == "SIGE nuevo" and stored["username"] is None and stored["url"] == "https://sige.mineduc.cl"
    assert c.post(f"{URL}/{cred_id}/reveal", headers=h).json() == {"password": SECRET}   # sin password: no cambia
    assert c.put(f"{URL}/{cred_id}", json={"password": "otra-clave-9"}, headers=h).status_code == 200
    assert c.post(f"{URL}/{cred_id}/reveal", headers=h).json() == {"password": "otra-clave-9"}
    c.delete(f"{URL}/{cred_id}", headers=h)
    log = db.audit_log.docs
    assert [d["action"] for d in log if d["action"] != "vault.reveal"] == ["vault.create", "vault.update", "vault.update", "vault.delete"]
    assert log[2]["changes"].get("password_changed") is True or log[3]["changes"].get("password_changed") is True
    assert "SIGE" in json.dumps(log, default=str)
    for secret in (SECRET, "otra-clave-9"):
        assert secret not in json.dumps(log, default=str)             # ni nueva ni antigua, en ninguna entrada


def test_BE65_delete_and_missing_ids(ctx):
    c, h, db = ctx
    cred_id = _create(c, h).json()["_id"]
    assert c.delete(f"{URL}/{cred_id}", headers=h).status_code == 204
    assert c.get(URL, headers=h).json() == []
    assert c.delete(f"{URL}/{cred_id}", headers=h).status_code == 404
    assert c.put(f"{URL}/no-es-un-id", json={"name": "x"}, headers=h).status_code == 404


@pytest.mark.parametrize("body", [
    {"name": "", "password": "x"},
    {"name": "SIGE", "password": ""},
    {"name": "SIGE", "password": "x", "url": "javascript:alert(1)"},   # solo http(s)
    {"name": "SIGE", "password": "x", "rbd": "9999"},                  # extra="forbid"
    {"name": "SIGE"},
])
def test_BE65_invalid_payloads_are_rejected(ctx, body):
    c, h, db = ctx
    assert c.post(URL, json=body, headers=h).status_code == 422
    assert db.vault_credentials.docs == []


# ── configuración ─────────────────────────────────────────────────────────────────────────
def test_BE65_invalid_vault_key_stops_startup():
    from tests.test_BE14_settings_fail_fast import VALID_ENV
    with pytest.raises(ConfigError, match="VAULT_KEY"):
        Settings({**VALID_ENV, "VAULT_KEY": "no-es-una-llave"})
