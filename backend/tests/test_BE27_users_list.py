"""
test_BE27_users_list.py
━━━━━━━━━━━━━━━━━━━━━━
Tarea: US-20 · Listar, buscar y filtrar usuarios (R5, D5, T1, T8)
"""
from datetime import datetime
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from tests.conftest import ADMIN_USER, DATOS_ADMIN_USER, prepare_org, bearer_for, _user, seed_users


@pytest.fixture
def ctx(fake_db):
    ids = prepare_org(fake_db, ADMIN_USER)
    people = [
        _user("6600000000000000000000e1", "ana.perez@slepllanquihue.cl", "Ana", "Pérez", [("datos", "editor")], unit_id=ids["AF-TI"]),
        _user("6600000000000000000000e2", "beto.rojas@slepllanquihue.cl", "Beto", "Rojas", [("datos", "viewer"), ("selloverde", "admin")], unit_id=ids["AF-FIN"]),
        _user("6600000000000000000000e3", "carla.soto@slepllanquihue.cl", "Carla", "Soto", [], unit_id=ids["SD-AF"], status="disabled"),
        _user("6600000000000000000000e4", "dario.vera@slepllanquihue.cl", "Darío", "Vera", [("datos", "viewer")], is_slep_staff=False,
              unit_id=None, rbd="7722", positions=["DOCENTE", "PIE_ENCARGADO"]),
        _user("6600000000000000000000e5", "elena.mora@slepllanquihue.cl", "Elena", "Mora", [], is_slep_staff=False,
              unit_id=None, rbd="7801", positions=["DIRECTOR"], status="invited",
              invitation={"sent_at": None, "expires_at": None, "last_error": "mail_not_configured"}),
    ]
    seed_users(fake_db, *people)
    from app.main import app
    return TestClient(app, raise_server_exceptions=True), ids, bearer_for(ADMIN_USER)


def emails(r):
    return sorted(i["email"] for i in r.json()["items"])


def test_BE27_envelope_and_page_size_limit_like_be04(ctx):
    c, ids, h = ctx
    r = c.get("/api/users?page_size=2&page=1", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"items", "total", "page", "page_size", "total_pages"}
    assert body["total"] == 6 and body["page_size"] == 2 and body["total_pages"] == 3 and len(body["items"]) == 2
    assert c.get("/api/users?page_size=201", headers=h).status_code == 422
    assert c.get("/api/users?page_size=200", headers=h).status_code == 200
    assert c.get("/api/users?page=0", headers=h).status_code == 422
    empty = c.get("/api/users?q=zzzz-nadie", headers=h).json()
    assert empty["total"] == 0 and empty["total_pages"] == 1 and empty["items"] == []         # nunca 0 páginas


def test_BE27_listing_projection_excludes_sensitive_fields(ctx):
    c, ids, h = ctx
    from app.users.users_service import USERS_LISTING_PROJECTION
    assert "personal_phone" not in USERS_LISTING_PROJECTION and "auth_providers" not in USERS_LISTING_PROJECTION
    assert all(v == 1 for v in USERS_LISTING_PROJECTION.values())                          # lista blanca de inclusión
    r = c.get("/api/users", headers=h)
    for item in r.json()["items"]:
        assert "personal_phone" not in item and "auth_providers" not in item
    assert "+56911112222" not in r.text and "hashed_password" not in r.text and "$2b$" not in r.text


def test_BE27_listing_is_sorted_by_last_name(ctx):
    c, ids, h = ctx
    names = [i["last_name"] for i in c.get("/api/users", headers=h).json()["items"]]
    assert names == sorted(names)


def test_BE27_search_is_escaped_literal(ctx):
    c, ids, h = ctx
    assert c.get("/api/users?q=ana", headers=h).json()["total"] == 1
    assert c.get("/api/users?q=ROJAS", headers=h).json()["total"] == 1                       # sin distinguir mayúsculas
    assert c.get("/api/users?q=beto.rojas@", headers=h).json()["total"] == 1
    for payload in (".*", "(a+)+$", "^", "[a-z]+", "a|b", "\\"):
        r = c.get("/api/users", params={"q": payload}, headers=h)
        assert r.status_code == 200 and r.json()["total"] == 0, payload                       # texto literal: no coincide con nadie


def test_BE27_search_rejects_operator_query_params(ctx):
    c, ids, h = ctx
    r = c.get("/api/users?q[$ne]=x", headers=h)
    assert r.status_code == 200 and r.json()["total"] == 6          # 'q[$ne]' es otro parámetro, ignorado: nunca un operador
    assert c.get("/api/users?q=" + "a" * 101, headers=h).status_code == 422


def test_BE27_unit_filter_with_and_without_descendants(ctx):
    c, ids, h = ctx
    only = c.get(f"/api/users?unit_id={ids['SD-AF']}", headers=h)
    assert emails(only) == ["carla.soto@slepllanquihue.cl"]
    tree = c.get(f"/api/users?unit_id={ids['SD-AF']}&include_descendants=true", headers=h)
    assert emails(tree) == ["ana.perez@slepllanquihue.cl", "beto.rojas@slepllanquihue.cl", "carla.soto@slepllanquihue.cl"]
    assert c.get(f"/api/users?unit_id={ids['AF-TI']}&include_descendants=true", headers=h).json()["total"] == 1


def test_BE27_filters_combine_with_and(ctx):
    c, ids, h = ctx
    assert emails(c.get("/api/users?kind=establishment", headers=h)) == ["dario.vera@slepllanquihue.cl", "elena.mora@slepllanquihue.cl"]
    assert emails(c.get("/api/users?kind=slep&status=active", headers=h)) == [
        "admin@slepllanquihue.cl", "ana.perez@slepllanquihue.cl", "beto.rojas@slepllanquihue.cl"]
    assert emails(c.get("/api/users?rbd=7722", headers=h)) == ["dario.vera@slepllanquihue.cl"]
    assert emails(c.get("/api/users?position=PIE_ENCARGADO", headers=h)) == ["dario.vera@slepllanquihue.cl"]
    assert emails(c.get("/api/users?platform=selloverde", headers=h)) == ["beto.rojas@slepllanquihue.cl"]
    assert emails(c.get("/api/users?platform=datos&role=viewer", headers=h)) == [
        "beto.rojas@slepllanquihue.cl", "dario.vera@slepllanquihue.cl"]
    assert emails(c.get("/api/users?platform=datos&role=viewer&kind=establishment", headers=h)) == ["dario.vera@slepllanquihue.cl"]
    assert emails(c.get(f"/api/users?level=4", headers=h)) == ["ana.perez@slepllanquihue.cl", "beto.rojas@slepllanquihue.cl"]
    assert emails(c.get(f"/api/users?level=3&status=disabled", headers=h)) == ["carla.soto@slepllanquihue.cl"]
    assert c.get("/api/users?status=cualquiera", headers=h).status_code == 422
    assert c.get("/api/users?position=INVENTADO", headers=h).status_code == 422
    assert c.get("/api/users?kind=otro", headers=h).status_code == 422


def test_BE27_items_expose_invitation_state(ctx):
    c, ids, h = ctx
    items = {i["email"]: i for i in c.get("/api/users?status=invited", headers=h).json()["items"]}
    inv = items["elena.mora@slepllanquihue.cl"]["invitation"]
    assert inv == {"sent_at": None, "expires_at": None, "last_error": "mail_not_configured", "sent": False}


def test_BE27_user_indexes_idempotent():
    import asyncio
    from unittest.mock import AsyncMock, MagicMock
    from app.database.database_service import DatabaseService
    svc = DatabaseService()
    svc.db = MagicMock()
    for name in ("establishments", "counterparts", "metrics", "users", "units"):
        setattr(svc.db, name, MagicMock(create_index=AsyncMock()))
    asyncio.run(svc.ensure_indexes()); asyncio.run(svc.ensure_indexes())
    keys = [str(c.args[0]) for c in svc.db.users.create_index.call_args_list[:9]]
    for field in ("email", "auth_providers.subject", "unit_id", "rbd", "positions", "access.platform_id", "status", "last_activity_at"):
        assert any(field in k for k in keys), f"falta el índice de users.{field}"
    email_call = next(c for c in svc.db.users.create_index.call_args_list if c.args[0] == "email")
    assert email_call.kwargs["unique"] is True and "partialFilterExpression" in email_call.kwargs


def test_BE27_non_iam_admin_forbidden(ctx, fake_db):
    c, ids, h = ctx
    seed_users(fake_db, DATOS_ADMIN_USER)
    assert c.get("/api/users", headers=bearer_for(DATOS_ADMIN_USER)).status_code == 403
    assert c.get("/api/users").status_code == 401
