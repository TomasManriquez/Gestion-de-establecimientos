"""
test_BE57_unassigned_accounts.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: S2 · Cuentas sin asignar (C24, G2) y configuración de la alta automática

Verifica que:
  - GET /api/users?assignment=unassigned lista solo las cuentas con `is_slep_staff` nulo (y solo para iam/admin)
  - el valor del filtro es un enum cerrado (cualquier otro da 422)
  - el alta manual y el CSV siguen exigiendo asignación (`is_slep_staff: null` da 422)
  - un usuario sin asignar se puede editar (nombre) sin romper el invariante
  - asignarlo exige indicar el modo; una vez asignado, un `null` en el PATCH no lo devuelve a «sin asignar»
  - GOOGLE_AUTO_PROVISION es obligatoria, sin default, y solo acepta true o false
"""
import pytest
from fastapi.testclient import TestClient
from app.config import ConfigError, Settings
from tests.conftest import ADMIN_USER, EDITOR_USER, VIEWER_USER, _user, bearer_for, prepare_org
from tests.test_BE14_settings_fail_fast import VALID_ENV

LOOSE = _user("6600000000000000000000c1", "suelta@slepllanquihue.cl", "Sue", "Lta", [("datos", "viewer")],
              is_slep_staff=None, unit_id=None)


@pytest.fixture
def ctx(fake_db):
    ids = prepare_org(fake_db, ADMIN_USER, EDITOR_USER, LOOSE)
    from app.main import app
    return TestClient(app), bearer_for(ADMIN_USER), fake_db, ids


def test_BE57_assignment_filter_lists_only_unassigned(ctx):
    c, h, db, ids = ctx
    r = c.get("/api/users?assignment=unassigned", headers=h)
    assert r.status_code == 200
    assert [u["email"] for u in r.json()["items"]] == [LOOSE["email"]]
    assert r.json()["items"][0]["is_slep_staff"] is None
    assert c.get("/api/users", headers=h).json()["total"] == 3


@pytest.mark.parametrize("value", ["assigned", "", "$ne", "unassigned%7C", "x" * 50])
def test_BE57_assignment_filter_is_a_closed_enum(ctx, value):
    c, h, db, ids = ctx
    assert c.get("/api/users", params={"assignment": value}, headers=h).status_code == 422


def test_BE57_assignment_filter_requires_global_admin(ctx):
    c, h, db, ids = ctx
    assert c.get("/api/users?assignment=unassigned", headers=bearer_for(EDITOR_USER)).status_code == 403


def test_BE57_manual_create_still_requires_assignment(ctx):
    c, h, db, ids = ctx
    body = {"email": "nuevo@slepllanquihue.cl", "first_name": "N", "last_name": "U", "is_slep_staff": None}
    assert c.post("/api/users", json=body, headers=h).status_code == 422
    assert c.post("/api/users/bulk-create", json={"items": [body], "dry_run": True}, headers=h).json()["failed"] == 1


def test_BE57_unassigned_user_can_be_renamed(ctx):
    c, h, db, ids = ctx
    r = c.patch(f"/api/users/{LOOSE['_id']}", json={"first_name": "Susana"}, headers=h)
    assert r.status_code == 200 and r.json()["first_name"] == "Susana" and r.json()["is_slep_staff"] is None


def test_BE57_assigning_requires_the_mode_and_is_one_way(ctx):
    c, h, db, ids = ctx
    url = f"/api/users/{LOOSE['_id']}"
    assert c.patch(url, json={"unit_id": ids["AF-TI"]}, headers=h).status_code == 422          # sin is_slep_staff
    ok = c.patch(url, json={"is_slep_staff": True, "unit_id": ids["AF-TI"]}, headers=h)
    assert ok.status_code == 200 and ok.json()["is_slep_staff"] is True
    back = c.patch(url, json={"is_slep_staff": None}, headers=h)                                 # null = «sin cambio»
    assert back.status_code == 200 and back.json()["is_slep_staff"] is True
    assert c.get("/api/users?assignment=unassigned", headers=h).json()["total"] == 0


def test_BE57_auto_provision_setting_is_required_and_strict():
    with pytest.raises(ConfigError, match="GOOGLE_AUTO_PROVISION"):
        Settings({k: v for k, v in VALID_ENV.items() if k != "GOOGLE_AUTO_PROVISION"})
    for bad in ("1", "yes", "si", "verdadero", "truee"):
        with pytest.raises(ConfigError, match="GOOGLE_AUTO_PROVISION"):
            Settings({**VALID_ENV, "GOOGLE_AUTO_PROVISION": bad})
    assert Settings({**VALID_ENV, "GOOGLE_AUTO_PROVISION": " TRUE "}).GOOGLE_AUTO_PROVISION is True
    assert Settings({**VALID_ENV, "GOOGLE_AUTO_PROVISION": "false"}).GOOGLE_AUTO_PROVISION is False
