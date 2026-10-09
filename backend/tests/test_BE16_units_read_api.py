"""
test_BE16_units_read_api.py
━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: US-09 · Consultar unidades y árbol (R2, R3, T3)
"""
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient
from tests.conftest import ADMIN_USER, VIEWER_USER, NO_DATOS_USER, prepare_org, bearer_for, _user


def client():
    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


def test_BE16_tree_is_nested_and_ordered_for_any_authenticated_user(fake_db):
    prepare_org(fake_db, ADMIN_USER, VIEWER_USER, NO_DATOS_USER)
    c = client()
    for user in (VIEWER_USER, NO_DATOS_USER, ADMIN_USER):
        r = c.get("/api/units/tree", headers=bearer_for(user))
        assert r.status_code == 200
        tree = r.json()
        assert len(tree) == 1 and tree[0]["code"] == "DE" and tree[0]["level"] == 1
        assert [n["code"] for n in tree[0]["children"]] == ["GAB", "JUR", "COM", "AUD", "SD-GP", "SD-AF", "SD-GT", "UATP", "SD-PC"]
        sdaf = next(n for n in tree[0]["children"] if n["code"] == "SD-AF")
        assert [n["code"] for n in sdaf["children"]] == ["AF-CL", "AF-TI", "AF-FIN"]
    assert c.get("/api/units/tree").status_code == 401


def test_BE16_flat_list_filters_and_response_model(fake_db):
    prepare_org(fake_db, VIEWER_USER)
    c = client()
    lvl4 = c.get("/api/units?level=4&status=active", headers=bearer_for(VIEWER_USER)).json()
    assert len(lvl4) == 13 and {u["level"] for u in lvl4} == {4}
    assert {"_id", "code", "name", "level", "parent_id", "ancestors", "head_user_id", "order", "status"} <= set(lvl4[0])
    assert c.get("/api/units?level=9", headers=bearer_for(VIEWER_USER)).status_code == 422
    assert c.get("/api/units?status=otro", headers=bearer_for(VIEWER_USER)).status_code == 422


def test_BE16_head_expansion_exposes_no_contact_data(fake_db):
    ids = prepare_org(fake_db)
    head = _user("6600000000000000000000c1", "jefa.ti@slepllanquihue.cl", "Julia", "Jefa", [], unit_id=ids["AF-TI"])
    from tests.conftest import seed_users
    seed_users(fake_db, VIEWER_USER, head)
    next(d for d in fake_db.units.docs if d["code"] == "AF-TI")["head_user_id"] = ObjectId(head["_id"])
    r = client().get("/api/units/tree?expand=head", headers=bearer_for(VIEWER_USER))
    assert r.status_code == 200
    assert "jefa.ti@" not in r.text and "+56911112222" not in r.text and "personal_phone" not in r.text
    def find(nodes, code):
        for n in nodes:
            if n["code"] == code:
                return n
            hit = find(n["children"], code)
            if hit:
                return hit
    ti = find(r.json(), "AF-TI")
    assert ti["head"] == {"id": head["_id"], "display_name": "Julia Jefa"}
    assert find(r.json(), "AF-FIN")["head"] is None


def test_BE16_invalid_object_id_is_client_error(fake_db):
    prepare_org(fake_db, VIEWER_USER)
    c = client()
    assert c.get("/api/units/no-es-un-id", headers=bearer_for(VIEWER_USER)).status_code == 404
    assert c.get("/api/units/%7B%22%24ne%22%3Anull%7D", headers=bearer_for(VIEWER_USER)).status_code == 404
    assert c.get("/api/units/6600000000000000000000ee", headers=bearer_for(VIEWER_USER)).status_code == 404


def test_BE16_get_unit_returns_materialized_ancestors(fake_db):
    ids = prepare_org(fake_db, VIEWER_USER)
    r = client().get(f"/api/units/{ids['AF-TI']}", headers=bearer_for(VIEWER_USER))
    assert r.status_code == 200 and r.json()["ancestors"] == [ids["DE"], ids["SD-AF"]]
    assert r.json()["parent_id"] == ids["SD-AF"]
