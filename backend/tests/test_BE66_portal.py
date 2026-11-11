"""
test_BE66_portal.py
━━━━━━━━━━━━━━━━━━━
ADR-021, fase 3 · Temas (dos niveles) y recursos del portal con visibilidad `org` / `restricted`.
"""
import pytest
from fastapi.testclient import TestClient

from app.portal.portal_service import detect_platform
from tests.conftest import ADMIN_USER, DATOS_ADMIN_USER, EDITOR_USER, VIEWER_USER, bearer_for, prepare_org

P = "/api/v1/portal"
CATS = {0: [], 1: ["staff"], 2: ["students"]}          # el nivel lo deduce el servidor de las categorías de datos
VIEWER_ID = str(VIEWER_USER["_id"])


@pytest.fixture
def ctx(fake_db):
    prepare_org(fake_db, ADMIN_USER, DATOS_ADMIN_USER, EDITOR_USER, VIEWER_USER)
    from app.main import app
    c = TestClient(app, raise_server_exceptions=True)
    admin = bearer_for(ADMIN_USER)
    topic = c.post(f"{P}/topics", json={"name": "Finanzas"}, headers=admin).json()["_id"]
    return c, admin, topic, fake_db


def _res(c, h, topic, level=1, **extra):
    body = {"title": "Tablero", "url": "https://app.powerbi.com/view?r=1", "topic_id": topic, "data_categories": CATS.get(level, [str(level)]), **extra}
    return c.post(f"{P}/resources", json=body, headers=h)


def _ids(c, h):
    return {r["_id"] for r in c.get(f"{P}/resources", headers=h).json()}


# ── temas ──────────────────────────────────────────────────────────────────────────────────
def test_BE66_topics_admin_only_two_levels_and_not_deleted_while_in_use(ctx):
    c, admin, topic, db = ctx
    editor = bearer_for(EDITOR_USER)
    assert c.post(f"{P}/topics", json={"name": "x"}, headers=editor).status_code == 403
    sub = c.post(f"{P}/topics", json={"name": "Presupuesto", "parent_id": topic}, headers=admin)
    assert sub.status_code == 201
    third = c.post(f"{P}/topics", json={"name": "Tercero", "parent_id": sub.json()["_id"]}, headers=admin)
    assert third.status_code == 422                                           # máximo dos niveles
    assert c.delete(f"{P}/topics/{topic}", headers=admin).status_code == 409  # tiene un subtema
    assert c.delete(f"{P}/topics/{sub.json()['_id']}", headers=admin).status_code == 204
    _res(c, admin, topic)
    assert c.delete(f"{P}/topics/{topic}", headers=admin).status_code == 409  # tiene un recurso
    assert {t["name"] for t in c.get(f"{P}/topics", headers=bearer_for(VIEWER_USER)).json()} == {"Finanzas"}


# ── visibilidad ────────────────────────────────────────────────────────────────────────────
def test_BE66_visibility_is_born_from_catastro_level(ctx):
    c, admin, topic, db = ctx
    assert _res(c, admin, topic, 0).json()["visibility"] == "org"
    assert _res(c, admin, topic, 1).json()["visibility"] == "org"
    assert _res(c, admin, topic, 2).json()["visibility"] == "restricted"


@pytest.mark.parametrize("cats,level", [([], 0), (["staff"], 1), (["internal"], 1), (["staff", "internal"], 1),
                                        (["students"], 2), (["sensitive"], 2), (["external"], 2), (["staff", "external"], 2)])
def test_BE66_level_is_derived_by_the_server_from_the_data_questionnaire(ctx, cats, level):
    c, admin, topic, db = ctx
    r = _res(c, admin, topic, 1, data_categories=cats).json()
    assert r["catastro_level"] == level and r["data_categories"] == sorted(cats)
    assert r["visibility"] == ("restricted" if level == 2 else "org")


def test_BE66_client_cannot_set_the_level_directly_or_send_unknown_categories(ctx):
    c, admin, topic, db = ctx
    base = {"title": "T", "url": "https://x.cl/a", "topic_id": topic}
    assert c.post(f"{P}/resources", json={**base, "catastro_level": 0}, headers=admin).status_code == 422
    assert c.post(f"{P}/resources", json={**base, "data_categories": ["otra"]}, headers=admin).status_code == 422
    rid = _res(c, admin, topic, 2)
    assert c.put(f"{P}/resources/{rid.json()['_id']}", json={"data_categories": []}, headers=admin).json()["catastro_level"] == 0


def test_BE66_registrar_sees_own_restricted_resource_and_others_do_not(ctx):
    c, admin, topic, db = ctx
    editor, viewer = bearer_for(EDITOR_USER), bearer_for(VIEWER_USER)
    rid = _res(c, editor, topic, 2).json()["_id"]
    assert rid in _ids(c, editor)                                             # el registrador lo ve de inmediato
    assert c.get(f"{P}/resources/{rid}", headers=editor).status_code == 200
    assert rid not in _ids(c, viewer)                                         # rol en datos no lo abre
    assert c.get(f"{P}/resources/{rid}", headers=viewer).status_code == 404   # y no revela que existe
    assert rid in _ids(c, admin)
    open_id = _res(c, admin, topic, 1).json()["_id"]
    assert open_id in _ids(c, viewer)                                         # `org` lo ve toda cuenta de datos
    g = c.post("/api/v1/access/grants", json={"resource_type": "portal_resource", "resource_id": rid, "user_id": VIEWER_ID},
               headers=admin)
    assert g.status_code == 201
    assert rid in _ids(c, viewer)


def test_BE66_filters_by_topic_and_requires_login(ctx):
    c, admin, topic, db = ctx
    other = c.post(f"{P}/topics", json={"name": "Compras"}, headers=admin).json()["_id"]
    a, b = _res(c, admin, topic).json()["_id"], _res(c, admin, other).json()["_id"]
    got = {r["_id"] for r in c.get(f"{P}/resources", params={"topic_id": other}, headers=admin).json()}
    assert got == {b} and a not in got
    assert c.get(f"{P}/resources").status_code == 401


# ── escritura ──────────────────────────────────────────────────────────────────────────────
def test_BE66_viewer_cannot_register_and_payload_is_validated(ctx):
    c, admin, topic, db = ctx
    assert _res(c, bearer_for(VIEWER_USER), topic).status_code == 403
    assert _res(c, admin, topic, url="javascript:alert(1)").status_code == 422
    assert _res(c, admin, topic, 3).status_code == 422
    assert _res(c, admin, "a" * 24).status_code == 422                        # tema inexistente
    assert _res(c, admin, topic, unit_id="b" * 24).status_code == 422         # unidad inexistente


def test_BE66_platform_is_detected_from_url(ctx):
    c, admin, topic, db = ctx
    assert _res(c, admin, topic).json()["platform"] == "Power BI"
    assert detect_platform("https://docs.google.com/spreadsheets/d/1/edit") == "Google Sheets"
    assert detect_platform("https://intranet.slep.cl/x") == "intranet.slep.cl"


def test_BE66_only_admin_or_creator_manages_and_only_admin_changes_visibility(ctx):
    c, admin, topic, db = ctx
    editor, other = bearer_for(EDITOR_USER), bearer_for(DATOS_ADMIN_USER)
    rid = _res(c, editor, topic, 1).json()["_id"]
    assert c.put(f"{P}/resources/{rid}", json={"title": "Nuevo"}, headers=other).status_code == 403
    assert c.put(f"{P}/resources/{rid}", json={"title": "Nuevo"}, headers=editor).json()["title"] == "Nuevo"
    assert c.put(f"{P}/resources/{rid}", json={"visibility": "restricted"}, headers=editor).status_code == 403
    assert c.put(f"{P}/resources/{rid}", json={"visibility": "restricted"}, headers=admin).json()["visibility"] == "restricted"
    # Ya restringido por el admin y sin concesión, hasta el creador deja de verlo: quien decide es el admin.
    assert c.put(f"{P}/resources/{rid}", json={"title": "Otro"}, headers=editor).status_code == 404


def test_BE66_raising_level_to_2_restricts_without_admin(ctx):
    c, admin, topic, db = ctx
    editor = bearer_for(EDITOR_USER)
    rid = _res(c, editor, topic, 0).json()["_id"]
    assert c.put(f"{P}/resources/{rid}", json={"data_categories": ["students"]}, headers=editor).json()["visibility"] == "restricted"
    assert rid not in _ids(c, bearer_for(VIEWER_USER))


def test_BE66_delete_purges_grants_and_is_audited(ctx):
    c, admin, topic, db = ctx
    editor = bearer_for(EDITOR_USER)
    rid = _res(c, editor, topic, 2).json()["_id"]
    assert len(db.resource_grants.docs) == 1                                  # la del registrador
    assert c.delete(f"{P}/resources/{rid}", headers=bearer_for(DATOS_ADMIN_USER)).status_code == 404
    assert c.delete(f"{P}/resources/{rid}", headers=editor).status_code == 204
    assert len(db.resource_grants.docs) == 0
    actions = {d["action"] for d in db.audit_log.docs}
    assert {"portal_resource.create", "portal_resource.delete", "resource_grant.create", "resource_grant.revoke"} <= actions
    assert c.get(f"{P}/resources/{rid}", headers=admin).status_code == 404
