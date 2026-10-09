"""
test_INT04_put_leak_and_marker_over_http.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: US-06 · El test que faltaba para la fuga por PUT (04 §4, D4), por HTTP real.
"""
import copy
import re
import pytest
from fastapi.testclient import TestClient
from tests.conftest import (EDITOR_USER, VIEWER_USER, SAMPLE_ESTABLISHMENT, seed_users, bearer_for)


@pytest.fixture
def client(fake_db):
    seed_users(fake_db, EDITOR_USER, VIEWER_USER)
    fake_db.establishments.seed(copy.deepcopy(SAMPLE_ESTABLISHMENT))
    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


def test_INT04_put_with_viewer_token_leaks_nothing(client):
    for body in ({}, {"name": "X"}):
        r = client.put("/api/establishments/7722", json=body, headers=bearer_for(VIEWER_USER))
        assert r.status_code == 403
        assert not re.search(r'"password"\s*:', r.text) and "clave-secreta" not in r.text
        assert "password-secreta" not in r.text


def test_INT04_put_empty_payload_by_editor_returns_document_for_authorized_role(client):
    """C20: el editor está autorizado a ver credenciales, así que el PUT vacío las devuelve."""
    r = client.put("/api/establishments/7722", json={}, headers=bearer_for(EDITOR_USER))
    assert r.status_code == 200
    assert r.json()["licenses"][0]["password"] == "clave-secreta-sige"


def test_INT04_viewer_detail_then_editor_put_roundtrip_keeps_real_secrets(client, fake_db):
    """El flujo de EditFicha: leer redactado y reenviar completo no destruye los secretos."""
    detail = client.get("/api/establishments/7722", headers=bearer_for(VIEWER_USER)).json()
    assert detail["licenses"][0]["password"] == "[REDACTED]"
    payload = {k: detail[k] for k in ("name", "licenses", "connectivity")}
    r = client.put("/api/establishments/7722", json=payload, headers=bearer_for(EDITOR_USER))
    assert r.status_code == 200
    assert fake_db.establishments.docs[0]["licenses"][0]["password"] == "clave-secreta-sige"
    assert fake_db.establishments.docs[0]["connectivity"]["ssid_password"] == "password-secreta-wifi"


def test_INT04_marker_without_stored_value_is_422_over_http(client, fake_db):
    fake_db.establishments.docs[0]["licenses"] = []
    payload = {"licenses": [{"name": "SIGE", "email": "", "password": "[REDACTED]", "url": "", "obs": "", "is_new": False}]}
    r = client.put("/api/establishments/7722", json=payload, headers=bearer_for(EDITOR_USER))
    assert r.status_code == 422 and "REDACTED" in r.json()["detail"]
