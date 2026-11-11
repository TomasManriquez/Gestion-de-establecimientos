"""
test_BE68_portal_cover.py
━━━━━━━━━━━━━━━━━━━━━━━━━
ADR-021 · Carátula (imagen) de un recurso del portal: solo PNG/JPEG/WebP ≤ 512 KB, con los permisos del recurso.
"""
import pytest
from fastapi.testclient import TestClient

from app.portal.portal_entity import COVER_MAX_BYTES
from tests.conftest import ADMIN_USER, DATOS_ADMIN_USER, EDITOR_USER, VIEWER_USER, bearer_for, prepare_org

P = "/api/v1/portal"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
JPG = b"\xff\xd8\xff\xe0" + b"0" * 64
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"0" * 64


@pytest.fixture
def ctx(fake_db):
    prepare_org(fake_db, ADMIN_USER, DATOS_ADMIN_USER, EDITOR_USER, VIEWER_USER)
    from app.main import app
    c = TestClient(app, raise_server_exceptions=True)
    admin = bearer_for(ADMIN_USER)
    topic = c.post(f"{P}/topics", json={"name": "Finanzas"}, headers=admin).json()["_id"]
    return c, admin, topic, fake_db


def _res(c, h, topic, level=1):
    return c.post(f"{P}/resources", json={"title": "Tablero", "url": "https://app.powerbi.com/x", "topic_id": topic,
                                          "catastro_level": level}, headers=h).json()["_id"]


def _put(c, h, rid, data, ctype="image/png"):
    return c.put(f"{P}/resources/{rid}/cover", content=data, headers={**h, "Content-Type": ctype})


@pytest.mark.parametrize("data,ctype", [(PNG, "image/png"), (JPG, "image/jpeg"), (WEBP, "image/webp")])
def test_BE68_creator_uploads_and_everyone_who_sees_it_downloads(ctx, data, ctype):
    c, admin, topic, db = ctx
    editor, viewer = bearer_for(EDITOR_USER), bearer_for(VIEWER_USER)
    rid = _res(c, editor, topic)
    assert c.get(f"{P}/resources/{rid}", headers=viewer).json()["has_cover"] is False
    assert c.get(f"{P}/resources/{rid}/cover", headers=viewer).status_code == 404
    r = _put(c, editor, rid, data, "application/octet-stream")                  # el tipo lo decide el contenido
    assert r.status_code == 200 and r.json()["has_cover"] is True
    got = c.get(f"{P}/resources/{rid}/cover", headers=viewer)
    assert got.status_code == 200 and got.content == data and got.headers["content-type"] == ctype
    assert got.headers["cache-control"].startswith("private") and got.headers["x-content-type-options"] == "nosniff"
    listed = c.get(f"{P}/resources", headers=viewer).json()
    assert listed[0]["has_cover"] is True and "cover_data" not in listed[0]     # la imagen no viaja en las listas


def test_BE68_only_real_small_images_are_accepted(ctx):
    c, admin, topic, db = ctx
    rid = _res(c, admin, topic)
    assert _put(c, admin, rid, b"<svg xmlns='http://www.w3.org/2000/svg'><script>1</script></svg>", "image/png").status_code == 422
    assert _put(c, admin, rid, b"GIF89a....", "image/gif").status_code == 422
    assert _put(c, admin, rid, PNG + b"0" * COVER_MAX_BYTES).status_code == 413
    assert db.portal_resources.docs[0].get("cover_data") is None


def test_BE68_permissions_follow_the_resource(ctx):
    c, admin, topic, db = ctx
    editor, other, viewer = bearer_for(EDITOR_USER), bearer_for(DATOS_ADMIN_USER), bearer_for(VIEWER_USER)
    rid = _res(c, editor, topic, level=1)
    assert _put(c, other, rid, PNG).status_code == 403                          # ni creador ni iam/admin
    assert _put(c, viewer, rid, PNG).status_code == 403                         # sin escritura en datos
    assert _put(c, editor, rid, PNG).status_code == 200
    secret = _res(c, editor, topic, level=2)
    assert _put(c, editor, secret, PNG).status_code == 200
    assert c.get(f"{P}/resources/{secret}/cover", headers=viewer).status_code == 404   # restringido: ni la carátula
    assert c.get(f"{P}/resources/{secret}/cover").status_code == 401


def test_BE68_remove_is_audited_and_resource_delete_drops_it(ctx):
    c, admin, topic, db = ctx
    editor = bearer_for(EDITOR_USER)
    rid = _res(c, editor, topic)
    _put(c, editor, rid, PNG)
    assert c.delete(f"{P}/resources/{rid}/cover", headers=editor).json()["has_cover"] is False
    assert c.get(f"{P}/resources/{rid}/cover", headers=editor).status_code == 404
    _put(c, editor, rid, PNG)
    covers = [d["changes"]["cover"] for d in db.audit_log.docs if d["action"] == "portal_resource.update"]
    assert covers == ["set", "removed", "set"]
    assert "cover_data" not in str(db.audit_log.docs)                           # los bytes no van al log
    assert c.delete(f"{P}/resources/{rid}", headers=editor).status_code == 204
    assert db.portal_resources.docs == []
