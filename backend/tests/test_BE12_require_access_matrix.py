"""
test_BE12_require_access_matrix.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: US-05 · `require_access` y matriz de roles (cierra D3 y D4) (C4, C5, C12, C14, C20, T3, T4)

Verifica la matriz de 04 §9.3 y que ninguna ruta se queda sin declarar su acceso.
"""
import copy
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from tests.conftest import (ADMIN_USER, DATOS_ADMIN_USER, EDITOR_USER, VIEWER_USER, NO_DATOS_USER,
                            SAMPLE_ESTABLISHMENT, SAMPLE_COUNTERPART, seed_users, bearer_for, _user)

CP_ID = "6600000000000000000000b1"


def setup(fake_db):
    seed_users(fake_db, ADMIN_USER, DATOS_ADMIN_USER, EDITOR_USER, VIEWER_USER, NO_DATOS_USER)
    fake_db.establishments.seed(copy.deepcopy(SAMPLE_ESTABLISHMENT))
    fake_db.counterparts.seed({**SAMPLE_COUNTERPART, "_id": ObjectId(CP_ID)})
    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


def test_BE12_viewer_put_establishment_forbidden(fake_db):
    c = setup(fake_db)
    r = c.put("/api/establishments/7722", json={"name": "HACKEADO"}, headers=bearer_for(VIEWER_USER))
    assert r.status_code == 403
    assert fake_db.establishments.docs[0]["name"] == SAMPLE_ESTABLISHMENT["name"]      # no se escribió


@pytest.mark.parametrize("method,path,body", [
    ("POST", "/api/counterparts", {"rbd": "7722", "role": "TI", "origin": "SLEP", "name": "X"}),
    ("PUT", f"/api/counterparts/{CP_ID}", {"name": "Y"}),
    ("DELETE", f"/api/counterparts/{CP_ID}", None),
    ("PUT", "/api/metrics/establishment/7722/2026", {"enrollment": 1}),
])
def test_BE12_viewer_cannot_write_counterparts_or_metrics(fake_db, method, path, body):
    c = setup(fake_db)
    r = c.request(method, path, json=body, headers=bearer_for(VIEWER_USER))
    assert r.status_code == 403
    assert fake_db.counterparts.calls == [] and fake_db.metrics.calls == []


def test_BE12_editor_writes_but_cannot_delete(fake_db):
    c = setup(fake_db)
    h = bearer_for(EDITOR_USER)
    assert c.put("/api/establishments/7722", json={"name": "NUEVO"}, headers=h).status_code == 200
    assert c.post("/api/counterparts", json={"rbd": "7722", "role": "TI", "origin": "SLEP", "name": "X"}, headers=h).status_code == 201
    assert c.put(f"/api/counterparts/{CP_ID}", json={"name": "Y"}, headers=h).status_code == 200
    assert c.put("/api/metrics/establishment/7722/2026", json={"enrollment": 5}, headers=h).status_code == 200
    r = c.delete(f"/api/counterparts/{CP_ID}", headers=h)
    assert r.status_code == 403
    assert fake_db.counterparts.docs[0]["_id"] == ObjectId(CP_ID)                      # sigue existiendo


def test_BE12_admin_can_delete_counterpart(fake_db):
    c = setup(fake_db)
    r = c.delete(f"/api/counterparts/{CP_ID}", headers=bearer_for(DATOS_ADMIN_USER))
    assert r.status_code == 200
    assert fake_db.counterparts.docs == []


@pytest.mark.parametrize("user,redacted", [(VIEWER_USER, True), (EDITOR_USER, False), (DATOS_ADMIN_USER, False)])
def test_BE12_detail_redaction_by_role(fake_db, user, redacted):
    c = setup(fake_db)
    d = c.get("/api/establishments/7722", headers=bearer_for(user)).json()
    pw, ssid = d["licenses"][0]["password"], d["connectivity"]["ssid_password"]
    if redacted:
        assert pw == ssid == "[REDACTED]"
    else:
        assert pw == "clave-secreta-sige" and ssid == "password-secreta-wifi"          # C20: el editor ve en claro


def test_BE12_controller_passes_include_sensitive_true_for_editor():
    import asyncio
    from unittest.mock import AsyncMock, patch
    from app.auth.auth_entity import AccessContext
    from app.establishments.establishments_controller import get_establishment_detail
    with patch("app.establishments.establishments_controller.establishments_service") as svc:
        svc.find_by_rbd = AsyncMock(return_value=copy.deepcopy(SAMPLE_ESTABLISHMENT))
        asyncio.run(get_establishment_detail(rbd="7722", ctx=AccessContext(user_id="u", role="editor")))
    assert svc.find_by_rbd.call_args.kwargs["include_sensitive"] is True


@pytest.mark.parametrize("path", ["/api/establishments", "/api/establishments/7722",
                                  "/api/counterparts/establishment/7722", "/api/metrics/establishment/7722",
                                  "/api/analytics/kpis"])
def test_BE12_user_without_datos_access_forbidden(fake_db, path):
    c = setup(fake_db)
    assert c.get(path, headers=bearer_for(NO_DATOS_USER)).status_code == 403


@pytest.mark.parametrize("method,path,body", [
    ("GET", "/api/users", None),
    ("POST", "/api/users", {"email": "x@slepllanquihue.cl", "first_name": "X", "last_name": "Y", "is_slep_staff": True, "unit_id": "6600000000000000000000f1"}),
    ("POST", "/api/units", {"code": "ZZ", "name": "Z", "level": 1}),
    ("GET", "/api/platforms", None),
    ("GET", "/api/users/6600000000000000000000a0", None),
])
def test_BE12_datos_admin_is_not_iam_admin(fake_db, method, path, body):
    c = setup(fake_db)
    assert c.request(method, path, json=body, headers=bearer_for(DATOS_ADMIN_USER)).status_code == 403
    assert c.request(method, path, json=body, headers=bearer_for(EDITOR_USER)).status_code == 403
    assert c.request(method, path, json=body, headers=bearer_for(VIEWER_USER)).status_code == 403


def test_BE12_unknown_role_grants_nothing(fake_db):
    seed_users(fake_db, _user("6600000000000000000000b9", "raro@slepllanquihue.cl", "Raro", "Rol", [("datos", "superuser")]))
    from app.main import app
    c = TestClient(app, raise_server_exceptions=False)
    h = bearer_for({"_id": "6600000000000000000000b9"})
    assert c.get("/api/establishments", headers=h).status_code == 403
    assert c.get("/api/users", headers=h).status_code == 403


def test_BE12_any_authenticated_user_can_read_me_and_units(fake_db):
    c = setup(fake_db)
    for user in (VIEWER_USER, NO_DATOS_USER):
        assert c.get("/api/auth/me", headers=bearer_for(user)).status_code == 200
        assert c.get("/api/users/me", headers=bearer_for(user)).status_code == 200


def _api_routes(app):
    """Rutas reales de la app. FastAPI reciente agrupa los routers incluidos en
    `_IncludedRouter` (con `original_router`); se recorren ambos casos."""
    for r in app.routes:
        if hasattr(r, "original_router"):
            yield from r.original_router.routes
        elif hasattr(r, "dependant"):
            yield r


def _declares_access(dependant):
    for d in dependant.dependencies:
        if hasattr(d.call, "__require_access__") or _declares_access(d):
            return True
    return False


PUBLIC_ROUTES = {
    ("GET", "/"),                                   # healthcheck de Docker/Nginx: público por diseño
    ("POST", "/api/auth/login"), ("POST", "/api/auth/login-form"), ("POST", "/api/auth/logout"),
    ("GET", "/api/auth/password-policy"),         # pública: la pantalla de definir contraseña no tiene sesión
}


def test_BE12_every_route_declares_access_or_is_allowlisted():
    from app.main import app
    routes = list(_api_routes(app))
    assert len(routes) >= 37, "no se encontraron las rutas de la app (¿cambió la estructura de FastAPI?)"
    missing = []
    for route in routes:
        for method in route.methods - {"HEAD", "OPTIONS"}:
            if (method, route.path) in PUBLIC_ROUTES:
                continue
            if not _declares_access(route.dependant):
                missing.append(f"{method} {route.path}")
    assert missing == [], f"Rutas sin require_access (L8/T3): {missing}"


def test_BE12_allowlist_has_no_stale_entries():
    from app.main import app
    existing = {(m, r.path) for r in _api_routes(app) for m in r.methods}
    assert PUBLIC_ROUTES <= existing
