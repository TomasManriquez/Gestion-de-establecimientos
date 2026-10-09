"""
test_INT03_role_matrix_over_http.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: US-05 · La matriz de 04 §9.3, ejecutada por HTTP real con tres tokens y sin token.
Correlaciones: BE12. Una celda errónea = una garantía de seguridad cambiada.
"""
import copy
from unittest.mock import AsyncMock, patch
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from tests.conftest import (ADMIN_USER, DATOS_ADMIN_USER, EDITOR_USER, VIEWER_USER, NO_DATOS_USER,
                            SAMPLE_ESTABLISHMENT, SAMPLE_COUNTERPART, seed_users, bearer_for)

CP_ID = "6600000000000000000000b1"
READ, WRITE, DELETE = "R", "W", "D"
ROUTES = [
    ("GET", "/api/establishments", None, READ),
    ("GET", "/api/establishments/7722", None, READ),
    ("PUT", "/api/establishments/7722", {"name": "NUEVO"}, WRITE),
    ("GET", "/api/counterparts/establishment/7722", None, READ),
    ("POST", "/api/counterparts", {"rbd": "7722", "role": "TI", "origin": "SLEP", "name": "X"}, WRITE),
    ("PUT", f"/api/counterparts/{CP_ID}", {"name": "Y"}, WRITE),
    ("DELETE", f"/api/counterparts/{CP_ID}", None, DELETE),
    ("GET", "/api/metrics/establishment/7722", None, READ),
    ("GET", "/api/metrics/establishment/7722/2026", None, READ),
    ("PUT", "/api/metrics/establishment/7722/2026", {"enrollment": 1}, WRITE),
    ("GET", "/api/analytics/kpis", None, READ),
    ("GET", "/api/analytics/charts", None, READ),
]
ALLOWED = {"viewer": {READ}, "editor": {READ, WRITE}, "admin": {READ, WRITE, DELETE}, "none": set()}
USERS = {"viewer": VIEWER_USER, "editor": EDITOR_USER, "admin": DATOS_ADMIN_USER, "none": NO_DATOS_USER}


@pytest.fixture
def client(fake_db):
    seed_users(fake_db, ADMIN_USER, DATOS_ADMIN_USER, EDITOR_USER, VIEWER_USER, NO_DATOS_USER)
    fake_db.establishments.seed(copy.deepcopy(SAMPLE_ESTABLISHMENT))
    fake_db.counterparts.seed({**SAMPLE_COUNTERPART, "_id": ObjectId(CP_ID)})
    from app.main import app
    with patch("app.analytics.analytics_controller.analytics_service") as svc:
        svc.get_kpis = AsyncMock(return_value={})
        svc.get_charts_data = AsyncMock(return_value={})
        yield TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("who", ["viewer", "editor", "admin", "none"])
@pytest.mark.parametrize("method,path,body,kind", ROUTES)
def test_INT03_role_matrix_over_http(client, who, method, path, body, kind):
    r = client.request(method, path, json=body, headers=bearer_for(USERS[who]))
    if kind in ALLOWED[who]:
        assert r.status_code not in (401, 403), f"{who} debería poder {method} {path}, recibió {r.status_code}"
    else:
        assert r.status_code == 403, f"{who} NO debería poder {method} {path}, recibió {r.status_code}"


@pytest.mark.parametrize("method,path,body,kind", ROUTES)
def test_INT03_anonymous_is_always_401(client, method, path, body, kind):
    r = client.request(method, path, json=body)
    assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"
