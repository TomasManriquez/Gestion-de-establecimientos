"""
test_INT08_injection_over_write_endpoints.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: transversal T1 · Inyección de operadores y asignación masiva en TODA ruta de escritura
de la feature. Recorre la tabla de rutas y reemplaza cada campo del body por un objeto de
operadores ({"$ne": null}): debe dar 422 y no escribir nada. Falla si aparece una ruta de
escritura nueva que no esté en la tabla (nadie se salta la revisión).
"""
import copy
import pytest
from fastapi.testclient import TestClient
from tests.conftest import ADMIN_USER, EDITOR_USER, prepare_org, bearer_for, run
from tests.test_BE12_require_access_matrix import _api_routes

UID = EDITOR_USER["_id"]
OPERATORS = ({"$ne": None}, {"$gt": ""}, [1], {"$where": "1"})


@pytest.fixture
def ctx(fake_db):
    ids = prepare_org(fake_db, ADMIN_USER, EDITOR_USER)
    from app.main import app
    return TestClient(app, raise_server_exceptions=True), ids, bearer_for(ADMIN_USER), fake_db


def table(ids):
    """(método, ruta, body válido, campos del body a corromper). Los params de ruta se prueban aparte."""
    u = {"email": "nuevo@slepllanquihue.cl", "first_name": "N", "last_name": "U", "is_slep_staff": True, "unit_id": ids["AF-TI"]}
    return [
        ("POST", "/api/users", u, list(u)),
        ("PATCH", f"/api/users/{UID}", {"first_name": "X", "last_name": "Y", "email": "z@slepllanquihue.cl"}, ["first_name", "last_name", "email"]),
        ("PATCH", "/api/users/me", {"personal_phone": "+56911112222", "work_extension": "123"}, ["personal_phone", "work_extension"]),
        ("PUT", f"/api/users/{UID}/access/datos", {"role": "viewer"}, ["role"]),
        ("POST", "/api/units", {"code": "NUEVA", "name": "Nueva", "level": 4, "parent_id": ids["SD-AF"]}, ["code", "name", "level", "parent_id"]),
        ("PATCH", f"/api/units/{ids['AF-TI']}", {"name": "Otro", "order": 3}, ["name", "order"]),
        ("POST", f"/api/units/{ids['AF-TI']}/move", {"parent_id": ids["SD-GP"]}, ["parent_id"]),
        ("PUT", f"/api/units/{ids['AF-TI']}/head", {"user_id": UID}, ["user_id"]),
        ("PATCH", "/api/platforms/selloverde", {"name": "X", "status": "inactive"}, ["name", "status"]),
        ("POST", "/api/auth/login", {"username": "a@slepllanquihue.cl", "password": "x"}, ["username", "password"]),
        ("POST", "/api/auth/password", {"current_password": "x", "new_password": "y"}, ["current_password", "new_password"]),
    ]


@pytest.mark.parametrize("operator", range(len(OPERATORS)))
def test_INT08_operator_objects_in_any_body_field_give_422(ctx, operator):
    c, ids, h, db = ctx
    snapshot = copy.deepcopy([(n, col.docs) for n, col in db._cols.items()])
    for method, path, body, fields in table(ids):
        for field in fields:
            bad = {**body, field: OPERATORS[operator]}
            r = c.request(method, path, json=bad, headers=h)
            assert r.status_code == 422, f"{method} {path} campo {field!r} con {OPERATORS[operator]!r} -> {r.status_code}"
    # nada se escribió (salvo la actividad de la sesión, que cambia por diseño)
    after = [(n, col.docs) for n, col in db._cols.items()]
    strip = lambda snap: [(n, [{k: v for k, v in d.items() if k != "last_activity_at"} for d in docs]) for n, docs in snap]
    assert strip(after) == strip(snapshot)


def test_INT08_unknown_extra_fields_give_422_on_every_write_body(ctx):
    c, ids, h, db = ctx
    for method, path, body, fields in table(ids):
        for extra in ("role", "status", "access", "hashed_password", "_id", "created_by", "ancestors", "roles"):
            r = c.request(method, path, json={**body, extra: "x"}, headers=h)
            assert r.status_code == 422, f"{method} {path} acepta el campo extra {extra!r} ({r.status_code})"


def test_INT08_every_write_route_of_the_feature_is_in_the_table(ctx):
    """Si alguien agrega una ruta de escritura sin pasar por esta revisión, este test falla."""
    c, ids, h, db = ctx
    from app.main import app
    covered = {(m, p) for m, p, *_ in table(ids)}
    norm = lambda p: p
    feature_prefixes = ("/api/users", "/api/units", "/api/platforms", "/api/auth")
    # rutas de escritura con body de la feature, normalizadas a plantilla
    templates = {
        ("POST", "/api/users"), ("PATCH", "/api/users/{user_id}"), ("PATCH", "/api/users/me"),
        ("PUT", "/api/users/{user_id}/access/{platform_id}"), ("POST", "/api/units"), ("PATCH", "/api/units/{unit_id}"),
        ("POST", "/api/units/{unit_id}/move"), ("PUT", "/api/units/{unit_id}/head"), ("PATCH", "/api/platforms/{platform_id}"),
        ("POST", "/api/auth/login"), ("POST", "/api/auth/password"),
    }
    # escrituras SIN body (acciones): no tienen campos que inyectar
    bodyless = {
        ("POST", "/api/users/{user_id}/disable"), ("POST", "/api/users/{user_id}/enable"),
        ("DELETE", "/api/users/{user_id}/access/{platform_id}"), ("POST", "/api/units/{unit_id}/deactivate"),
        ("POST", "/api/units/{unit_id}/activate"), ("POST", "/api/auth/logout"), ("POST", "/api/auth/login-form"),
    }
    actual = {(m, r.path) for r in _api_routes(app) for m in r.methods
              if m in ("POST", "PUT", "PATCH", "DELETE") and r.path.startswith(feature_prefixes)}
    unknown = actual - templates - bodyless
    assert unknown == set(), f"Rutas de escritura sin revisar contra inyección (T1): {sorted(unknown)}"
    assert len(covered) == len(templates)


def test_INT08_path_params_with_operators_never_reach_the_database(ctx):
    c, ids, h, db = ctx
    for evil in ("%7B%22%24ne%22%3Anull%7D", "%24ne", "..%2F..%2Fetc", "6600000000000000000000zz", "x" * 300):
        for method, path in (("GET", "/api/users/{}"), ("PATCH", "/api/users/{}"), ("POST", "/api/users/{}/disable"),
                             ("GET", "/api/units/{}"), ("POST", "/api/units/{}/deactivate"), ("PUT", "/api/users/{}/access/datos")):
            body = {"first_name": "X"} if method == "PATCH" else ({"role": "viewer"} if method == "PUT" else None)
            r = c.request(method, path.format(evil), json=body, headers=h)
            assert r.status_code in (404, 422), (method, path, evil, r.status_code)
