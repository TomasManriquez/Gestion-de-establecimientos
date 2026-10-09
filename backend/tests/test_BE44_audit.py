"""
test_BE44_audit.py
━━━━━━━━━━━━━━━━━━
Tarea: US-45 · Auditoría de solo agregado (ADR-014)

Verifica que:
  - cada cambio de usuarios, accesos, unidades y plataformas deja un registro con actor y {campo: [antes, después]}
  - `changes` jamás lleva credenciales, y el teléfono personal queda enmascarado
  - una operación fallida (409) o sin cambios no deja registro
  - el módulo no tiene ninguna operación que edite o borre (ni en el service ni en las rutas)
  - si la escritura de auditoría falla, el cambio persiste, se registra CRITICAL y la respuesta lleva X-Audit-Status
  - GET /api/audit es solo de iam/admin, filtra y pagina
  - la creación de varios usuarios comparte bulk_id; una alta suelta no lo lleva
"""
import ast
import json
import logging
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from tests.conftest import ADMIN_USER, EDITOR_USER, _user, bearer_for, prepare_org, run

APP = Path(__file__).resolve().parents[1] / "app"
TARGET = _user("6600000000000000000000e9", "nuevo@slepllanquihue.cl", "Nuevo", "Usuario", [])


@pytest.fixture
def ctx(fake_db):
    ids = prepare_org(fake_db, ADMIN_USER, EDITOR_USER, TARGET)
    from app.main import app
    return TestClient(app, raise_server_exceptions=True), bearer_for(ADMIN_USER), fake_db, ids


def entries(db, **match):
    return [d for d in db.audit_log.docs if all(d.get(k) == v for k, v in match.items())]


def last(db):
    return db.audit_log.docs[-1]


# ── saneamiento ───────────────────────────────────────────────────────────────
def test_BE44_clean_changes_drops_secrets_masks_phone_and_plainifies():
    from app.audit.audit_service import clean_changes
    from app.users.users_entity import UserStatus
    out = clean_changes({
        "hashed_password": ["a", "b"], "Password": "x", "token_hash": "y", "refresh_token": "z",
        "personal_phone": ["+56911111111", "+56922222222"],
        "status": [UserStatus.ACTIVE, UserStatus.DISABLED], "unit_id": [None, ObjectId("6600000000000000000000a0")],
        "nested": {"client_secret": "s", "ok": 1},
    })
    assert out == {"personal_phone": ["[REDACTED]", "[REDACTED]"], "status": ["active", "disabled"],
                   "unit_id": [None, "6600000000000000000000a0"], "nested": {"ok": 1}}


def test_BE44_diff_only_lists_changed_fields():
    from app.audit.audit_service import diff
    assert diff({"a": 1, "b": 2}, {"a": 1, "b": 3}, ["a", "b", "c"]) == {"b": [2, 3]}


# ── solo agregado ─────────────────────────────────────────────────────────────
def test_BE44_service_has_no_edit_or_delete_operation():
    from app.audit.audit_service import AuditService
    public = {n for n in dir(AuditService) if not n.startswith("_")}
    assert public == {"record", "list_entries", "new_bulk_id"}
    src = (APP / "audit" / "audit_service.py").read_text(encoding="utf-8")
    attrs = {n.attr for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Attribute)}
    assert not attrs & {"update_one", "update_many", "delete_one", "delete_many", "replace_one",
                        "find_one_and_update", "find_one_and_delete", "find_one_and_replace", "drop", "bulk_write"}


def test_BE44_only_get_routes_exist_for_audit():
    from app.audit.audit_controller import router
    assert {m for r in router.routes for m in r.methods} == {"GET"}


def test_BE44_audit_module_has_exactly_three_files_and_imports_no_domain_module():
    files = {p.name for p in (APP / "audit").iterdir() if p.suffix == ".py"}
    assert files == {"__init__.py", "audit_entity.py", "audit_service.py", "audit_controller.py"}
    for name in ("audit_entity.py", "audit_service.py"):
        tree = ast.parse((APP / "audit" / name).read_text(encoding="utf-8"))
        mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        domain = {m for m in mods if m.startswith("app.") and not m.startswith(("app.audit", "app.database", "app.config"))}
        assert not domain, f"{name} importa {domain}"


# ── registros por operación ───────────────────────────────────────────────────
def test_BE44_user_create_update_disable_enable_and_access_are_audited(ctx):
    c, h, db, ids = ctx
    r = c.post("/api/users", json={"first_name": "Pia", "last_name": "Rojas", "email": "pia.rojas@slepllanquihue.cl",
                                   "is_slep_staff": True, "unit_id": ids["AF-TI"], "personal_phone": "+56911112222"}, headers=h)
    assert r.status_code == 201
    uid = r.json()["id"] if "id" in r.json() else r.json()["_id"]
    created = next(d for d in db.audit_log.docs if d["action"] == "user.create")
    assert created["target_id"] == uid
    assert last(db)["action"] == "user.invite" and last(db)["changes"] == {"invitation": [None, "sent"]}
    assert created["actor_id"] == ObjectId(ADMIN_USER["_id"]) and created["bulk_id"] is None
    assert created["changes"]["email"] == [None, "pia.rojas@slepllanquihue.cl"]

    assert c.patch(f"/api/users/{uid}", json={"last_name": "Rojas Soto", "personal_phone": "+56933334444"}, headers=h).status_code == 200
    upd = last(db)
    assert upd["action"] == "user.update"
    assert upd["changes"]["last_name"] == ["Rojas", "Rojas Soto"]
    assert upd["changes"]["personal_phone"] == ["[REDACTED]", "[REDACTED]"]

    assert c.put(f"/api/users/{uid}/access/datos", json={"role": "viewer"}, headers=h).status_code == 200
    assert (last(db)["action"], last(db)["changes"]) == ("access.grant", {"platform_id": "datos", "role": [None, "viewer"]})
    assert c.put(f"/api/users/{uid}/access/datos", json={"role": "editor"}, headers=h).status_code == 200
    assert last(db)["changes"]["role"] == ["viewer", "editor"]
    assert c.delete(f"/api/users/{uid}/access/datos", headers=h).status_code == 200
    assert (last(db)["action"], last(db)["changes"]["role"]) == ("access.revoke", ["editor", None])

    assert c.post(f"/api/users/{uid}/disable", headers=h).status_code == 200
    assert (last(db)["action"], last(db)["changes"]) == ("user.disable", {"status": ["invited", "disabled"]})
    assert c.post(f"/api/users/{uid}/enable", headers=h).status_code == 200
    assert (last(db)["action"], last(db)["changes"]) == ("user.enable", {"status": ["disabled", "invited"]})


def test_BE44_failed_and_noop_operations_leave_no_record(ctx):
    c, h, db, ids = ctx
    before = len(db.audit_log.docs)
    # 409: duplicado
    r = c.post("/api/users", json={"first_name": "X", "last_name": "Y", "email": EDITOR_USER["email"],
                                   "is_slep_staff": True, "unit_id": ids["AF-TI"]}, headers=h)
    assert r.status_code == 409
    # 409: el último admin global no puede desactivarse a sí mismo / perder el acceso
    assert c.post(f"/api/users/{ADMIN_USER['_id']}/disable", headers=h).status_code == 409
    assert c.delete(f"/api/users/{ADMIN_USER['_id']}/access/iam", headers=h).status_code == 409
    # sin cambios reales
    assert c.patch(f"/api/users/{EDITOR_USER['_id']}", json={"first_name": EDITOR_USER["first_name"]}, headers=h).status_code == 200
    assert c.put(f"/api/users/{EDITOR_USER['_id']}/access/datos", json={"role": "editor"}, headers=h).status_code == 200
    assert c.delete(f"/api/users/{EDITOR_USER['_id']}/access/selloverde", headers=h).status_code == 200
    assert len(db.audit_log.docs) == before


def test_BE44_units_and_platforms_are_audited(ctx):
    c, h, db, ids = ctx
    r = c.post("/api/units", json={"code": "AF-NEW", "name": "Unidad Nueva", "level": 4, "parent_id": ids["SD-AF"], "order": 9}, headers=h)
    assert r.status_code == 201
    uid = r.json()["id"] if "id" in r.json() else r.json()["_id"]
    assert (last(db)["action"], last(db)["target_type"], last(db)["target_id"]) == ("unit.create", "unit", uid)
    assert c.patch(f"/api/units/{uid}", json={"name": "Unidad Renombrada"}, headers=h).status_code == 200
    assert last(db)["changes"]["name"] == ["Unidad Nueva", "Unidad Renombrada"]
    assert c.post(f"/api/units/{uid}/move", json={"parent_id": ids["SD-GT"]}, headers=h).status_code == 200
    assert (last(db)["action"], last(db)["changes"]["parent_id"]) == ("unit.move", [ids["SD-AF"], ids["SD-GT"]])
    assert c.post(f"/api/units/{uid}/deactivate", headers=h).status_code == 200
    assert (last(db)["action"], last(db)["changes"]) == ("unit.deactivate", {"status": ["active", "inactive"]})
    assert c.post(f"/api/units/{uid}/activate", headers=h).status_code == 200
    assert last(db)["action"] == "unit.activate"
    assert c.put(f"/api/units/{ids['AF-TI']}/head", json={"user_id": None}, headers=h).status_code == 200
    assert last(db)["action"] == "unit.head"

    assert c.patch("/api/platforms/selloverde", json={"name": "Sello Verde 2"}, headers=h).status_code == 200
    assert (last(db)["action"], last(db)["target_type"], last(db)["target_id"]) == ("platform.update", "platform", "selloverde")
    assert last(db)["changes"]["name"][1] == "Sello Verde 2"


def test_BE44_no_credential_ever_reaches_the_log(ctx):
    c, h, db, ids = ctx
    c.post("/api/users", json={"first_name": "Pia", "last_name": "Rojas", "email": "pia.rojas@slepllanquihue.cl",
                               "is_slep_staff": True, "unit_id": ids["AF-TI"]}, headers=h)
    c.post("/api/auth/password", json={"current_password": "x" * 20, "new_password": "una-clave-nueva-muy-larga-123"}, headers=h)
    text = json.dumps(db.audit_log.docs, default=str)
    for needle in ("$2b$", "hashed_password", "password", "token_hash"):
        assert needle not in text


def test_BE44_bulk_id_is_shared_only_by_multi_user_creates(ctx):
    from app.users.users_service import users_service
    c, h, db, ids = ctx
    rows = [{"first_name": f"U{i}", "last_name": "Masivo", "email": f"u{i}@slepllanquihue.cl",
             "is_slep_staff": True, "unit_id": ids["AF-TI"]} for i in range(3)]
    result = run(users_service.create_many(rows, ADMIN_USER["_id"]))
    created = [d for d in db.audit_log.docs if d["action"] == "user.create"]
    assert len(created) == 3 and {d["bulk_id"] for d in created} == {result["bulk_id"]}
    run(users_service.create_many(rows[:1] and [{**rows[0], "email": "solo@slepllanquihue.cl"}], ADMIN_USER["_id"]))
    assert db.audit_log.docs[-1]["bulk_id"] is None
    # un dry-run no escribe nada
    n = len(db.audit_log.docs)
    run(users_service.create_many([{**rows[0], "email": "ensayo@slepllanquihue.cl"}], ADMIN_USER["_id"], dry_run=True))
    assert len(db.audit_log.docs) == n


def test_BE44_bootstrap_admin_creation_is_recorded_as_a_system_action(fake_db):
    from app.users.users_service import users_service
    from app.units.units_service import units_service
    from app.platforms.platforms_service import platforms_service
    run(units_service.ensure_bootstrap_units()); run(platforms_service.ensure_bootstrap_platforms())
    run(users_service.ensure_bootstrap_admin("admin@slepllanquihue.cl", lambda: "hash"))
    rec = fake_db.audit_log.docs
    assert len(rec) == 1 and rec[0]["action"] == "user.create" and rec[0]["actor_id"] is None


# ── fallo de la auditoría ─────────────────────────────────────────────────────
def test_BE44_audit_failure_does_not_revert_the_change_and_is_signalled(ctx, caplog):
    c, h, db, ids = ctx
    ok = c.post(f"/api/users/{EDITOR_USER['_id']}/disable", headers=h)
    assert ok.status_code == 200 and "x-audit-status" not in ok.headers
    c.post(f"/api/users/{EDITOR_USER['_id']}/enable", headers=h)
    with patch.object(db.audit_log, "insert_one", AsyncMock(side_effect=RuntimeError("mongo caído"))):
        with caplog.at_level(logging.CRITICAL, logger="audit"):
            r = c.post(f"/api/users/{EDITOR_USER['_id']}/disable", headers=h)
    assert r.status_code == 200 and r.headers["x-audit-status"] == "failed"
    assert next(d for d in db.users.docs if str(d["_id"]) == EDITOR_USER["_id"])["status"] == "disabled"
    assert any(rec.levelno == logging.CRITICAL for rec in caplog.records)
    # la petición siguiente vuelve a ser normal (el aviso es por petición)
    again = c.post(f"/api/users/{EDITOR_USER['_id']}/enable", headers=h)
    assert "x-audit-status" not in again.headers


def test_BE44_record_never_raises(fake_db):
    from app.audit.audit_entity import AuditAction, AuditTarget
    from app.audit.audit_service import audit_service
    with patch.object(fake_db.audit_log, "insert_one", AsyncMock(side_effect=RuntimeError("x"))):
        assert run(audit_service.record(None, AuditAction.USER_CREATE, AuditTarget.USER, "1", {"a": [1, 2]})) is False
    assert run(audit_service.record(None, AuditAction.USER_CREATE, AuditTarget.USER, "1", {"a": [1, 2]})) is True


# ── consulta ──────────────────────────────────────────────────────────────────
def test_BE44_audit_endpoint_is_iam_admin_only(ctx):
    c, h, db, ids = ctx
    assert c.get("/api/audit").status_code == 401
    assert c.get("/api/audit", headers=bearer_for(EDITOR_USER)).status_code == 403
    assert c.get("/api/audit", headers=h).status_code == 200


def test_BE44_audit_list_filters_orders_and_paginates(ctx):
    c, h, db, ids = ctx
    for role in ("viewer", "editor", "viewer"):
        c.put(f"/api/users/{TARGET['_id']}/access/datos", json={"role": role}, headers=h)
    c.post(f"/api/users/{TARGET['_id']}/disable", headers=h)
    body = c.get("/api/audit", headers=h).json()
    assert body["total"] == 4 and [e["action"] for e in body["items"]][0] == "user.disable"     # más reciente primero
    assert body["items"][0]["actor_id"] == ADMIN_USER["_id"]
    only = c.get("/api/audit", params={"action": "access.grant", "target_id": TARGET["_id"]}, headers=h).json()
    assert only["total"] == 3
    assert c.get("/api/audit", params={"actor_id": EDITOR_USER["_id"]}, headers=h).json()["total"] == 0
    p2 = c.get("/api/audit", params={"page": 2, "page_size": 3}, headers=h).json()
    assert len(p2["items"]) == 1 and p2["total_pages"] == 2
    assert c.get("/api/audit", params={"page_size": 201}, headers=h).status_code == 422
    assert c.get("/api/audit", params={"action": "user.exploded"}, headers=h).status_code == 422
    assert c.get("/api/audit", params={"actor_id": "zzzzzzzzzzzzzzzzzzzzzzzz"}, headers=h).json()["total"] == 0
    assert c.get("/api/audit", params={"since": "2999-01-01T00:00:00"}, headers=h).json()["total"] == 0
    assert c.get("/api/audit", params={"until": "2999-01-01T00:00:00Z"}, headers=h).json()["total"] == 4
