"""
test_BE49_subrogations_and_counterpart_link.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: US-19..US-21 (subrogancias, prioridad Could) y US-22 (vínculo opcional contraparte ↔ usuario, ADR-011)

Verifica que:
  - solo iam/admin registra y cancela subrogancias; leerlas lo puede hacer cualquier usuario autenticado
  - el subrogante es un funcionario SLEP activo, de la unidad o su subárbol, y no la jefatura titular
  - no se superponen dos vigentes en una unidad; `ends_at` es obligatorio salvo en una VACANCIA
  - «vigente» se calcula por fecha (sin jobs) y cancelar es idempotente
  - registrar una subrogancia NO concede ningún permiso
  - el filtro `acting` del listado de usuarios devuelve solo a quienes subrogan hoy
  - `counterparts.user_id` es opcional, se valida contra `users` y se desvincula con ""
  - el script de backfill es un ensayo por defecto y solo empareja por correo normalizado
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from tests.conftest import (ADMIN_USER, EDITOR_USER, SAMPLE_COUNTERPART, _user, bearer_for, prepare_org, run, seed_users)

NOW = datetime.now(timezone.utc).replace(tzinfo=None)
iso = lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%S")
JEFA, SUB_TI, SUB_FIN, SUB_INACTIVA, SUB_COLEGIO, SUB_PADRE = (f"6600000000000000000000d{i}" for i in range(1, 7))


@pytest.fixture
def ctx(fake_db):
    ids = prepare_org(fake_db, ADMIN_USER, EDITOR_USER)
    seed_users(fake_db,
               _user(JEFA, "jefa@slepllanquihue.cl", "Julia", "Jefa", [], unit_id=ids["SD-AF"]),
               _user(SUB_TI, "subti@slepllanquihue.cl", "Sara", "TI", [], unit_id=ids["AF-TI"]),
               _user(SUB_FIN, "subfin@slepllanquihue.cl", "Saul", "Fin", [], unit_id=ids["AF-FIN"]),
               _user(SUB_INACTIVA, "inactiva@slepllanquihue.cl", "Ines", "Inactiva", [], unit_id=ids["AF-TI"], status="disabled"),
               _user(SUB_COLEGIO, "colegio@slepllanquihue.cl", "Carlos", "Colegio", [], is_slep_staff=False, unit_id=None,
                     rbd="7722", positions=["DOCENTE"]),
               _user(SUB_PADRE, "padre@slepllanquihue.cl", "Pablo", "Padre", [], unit_id=ids["DE"]))
    from app.main import app
    c = TestClient(app, raise_server_exceptions=True)
    assert c.put(f"/api/units/{ids['SD-AF']}/head", json={"user_id": JEFA}, headers=bearer_for(ADMIN_USER)).status_code == 200
    return c, bearer_for(ADMIN_USER), fake_db, ids


def body(user=SUB_TI, starts=None, ends="auto", reason="VACACIONES", **kw):
    starts = starts or NOW - timedelta(days=1)
    ends = starts + timedelta(days=10) if ends == "auto" else ends
    return {"subrogate_user_id": user, "starts_at": iso(starts), "ends_at": iso(ends) if ends else None, "reason": reason, **kw}


def post(c, h, unit, **kw):
    return c.post(f"/api/units/{unit}/subrogations", json=body(**kw), headers=h)


# ── registrar ─────────────────────────────────────────────────────────────────
def test_BE49_create_returns_the_document_and_computes_current(ctx):
    c, h, db, ids = ctx
    r = post(c, h, ids["SD-AF"], document_ref="Resolución Exenta N° 123")
    assert r.status_code == 201
    s = r.json()
    assert s["unit_id"] == ids["SD-AF"] and s["subrogate_user_id"] == SUB_TI and s["reason"] == "VACACIONES"
    assert s["current"] is True and s["cancelled_at"] is None and s["created_by"] == ADMIN_USER["_id"]
    assert s["document_ref"] == "Resolución Exenta N° 123"


def test_BE49_future_and_past_subrogations_are_not_current(ctx):
    c, h, db, ids = ctx
    future = post(c, h, ids["SD-AF"], starts=NOW + timedelta(days=30)).json()
    past = post(c, h, ids["AF-TI"], starts=NOW - timedelta(days=60), ends=NOW - timedelta(days=50)).json()
    assert future["current"] is False and past["current"] is False
    assert post(c, h, ids["AF-TI"], starts=NOW - timedelta(days=1), ends=NOW + timedelta(days=1)).json()["current"] is True


@pytest.mark.parametrize("user,code", [
    (SUB_INACTIVA, "subrogate_inactive"), (SUB_COLEGIO, "head_not_slep_staff"), (SUB_FIN, "subrogate_not_member"),
    (JEFA, None),
])
def test_BE49_subrogate_rules(ctx, user, code):
    c, h, db, ids = ctx
    unit = ids["AF-TI"] if user != JEFA else ids["SD-AF"]
    r = post(c, h, unit, user=user)
    if user == JEFA:
        assert r.status_code == 409 and r.json()["detail"]["code"] == "subrogate_is_head"
    else:
        assert r.status_code == 409 and r.json()["detail"]["code"] == code
    assert db.subrogations.docs == []


def test_BE49_subrogate_may_come_from_the_subtree_but_not_from_above(ctx):
    c, h, db, ids = ctx
    assert post(c, h, ids["SD-AF"], user=SUB_FIN).status_code == 201                    # AF-FIN cuelga de SD-AF
    assert post(c, h, ids["AF-TI"], user=SUB_PADRE).json()["detail"]["code"] == "subrogate_not_member"   # la raíz no es subárbol de AF-TI


def test_BE49_unknown_unit_user_and_inactive_unit(ctx):
    c, h, db, ids = ctx
    assert post(c, h, "6600000000000000000000ff").status_code == 404
    assert post(c, h, "no-es-un-id").status_code == 404
    assert post(c, h, ids["AF-TI"], user="6600000000000000000000fe").status_code == 404
    next(d for d in db.units.docs if d["code"] == "AF-TI")["status"] = "inactive"
    assert post(c, h, ids["AF-TI"]).json()["detail"]["code"] == "inactive_unit"


def test_BE49_ends_at_required_except_for_vacancy(ctx):
    c, h, db, ids = ctx
    assert post(c, h, ids["SD-AF"], ends=None).status_code == 422                          # VACACIONES sin fin
    assert post(c, h, ids["SD-AF"], ends=NOW - timedelta(days=5)).status_code == 422       # fin antes del inicio
    open_ended = post(c, h, ids["SD-AF"], ends=None, reason="VACANCIA")
    assert open_ended.status_code == 201 and open_ended.json()["ends_at"] is None and open_ended.json()["current"] is True


def test_BE49_overlapping_subrogations_are_rejected(ctx):
    c, h, db, ids = ctx
    assert post(c, h, ids["SD-AF"], starts=NOW, ends=NOW + timedelta(days=10)).status_code == 201
    dup = post(c, h, ids["SD-AF"], user=SUB_FIN, starts=NOW + timedelta(days=5), ends=NOW + timedelta(days=15))
    assert dup.status_code == 409 and dup.json()["detail"]["code"] == "subrogation_overlap"
    assert post(c, h, ids["SD-AF"], user=SUB_FIN, starts=NOW + timedelta(days=10), ends=NOW + timedelta(days=20)).status_code == 201   # contiguas
    assert post(c, h, ids["AF-TI"], user=SUB_TI, starts=NOW, ends=NOW + timedelta(days=10)).status_code == 201                       # otra unidad
    # una abierta (VACANCIA) bloquea cualquier fecha posterior
    assert post(c, h, ids["SD-AF"], user=SUB_TI, starts=NOW + timedelta(days=40), ends=None, reason="VACANCIA").status_code == 201
    assert post(c, h, ids["SD-AF"], user=SUB_FIN, starts=NOW + timedelta(days=90), ends=NOW + timedelta(days=95)).status_code == 409


def test_BE49_cancelled_subrogation_frees_the_period_and_cancel_is_idempotent(ctx):
    c, h, db, ids = ctx
    sid = post(c, h, ids["SD-AF"]).json()["_id"]
    r = c.post(f"/api/units/subrogations/{sid}/cancel", headers=h)
    assert r.status_code == 200 and r.json()["cancelled_at"] and r.json()["current"] is False
    first = r.json()["cancelled_at"]
    assert c.post(f"/api/units/subrogations/{sid}/cancel", headers=h).json()["cancelled_at"] == first      # idempotente
    assert post(c, h, ids["SD-AF"], user=SUB_FIN).status_code == 201                                       # el periodo quedó libre
    assert c.post("/api/units/subrogations/6600000000000000000000ff/cancel", headers=h).status_code == 404
    assert c.post("/api/units/subrogations/no-es-un-id/cancel", headers=h).status_code == 404


# ── lectura y acceso ──────────────────────────────────────────────────────────
def test_BE49_listing_orders_filters_and_is_open_to_any_authenticated_user(ctx):
    c, h, db, ids = ctx
    post(c, h, ids["SD-AF"], starts=NOW - timedelta(days=90), ends=NOW - timedelta(days=80))
    post(c, h, ids["SD-AF"], starts=NOW - timedelta(days=1))
    viewer = bearer_for(EDITOR_USER)
    items = c.get(f"/api/units/{ids['SD-AF']}/subrogations", headers=viewer).json()
    assert len(items) == 2 and items[0]["current"] is True and items[1]["current"] is False        # más reciente primero
    assert [i["current"] for i in c.get(f"/api/units/{ids['SD-AF']}/subrogations?current=true", headers=viewer).json()] == [True]
    assert c.get(f"/api/units/{ids['SD-AF']}/subrogations").status_code == 401
    assert c.get("/api/units/6600000000000000000000ff/subrogations", headers=viewer).status_code == 404


def test_BE49_only_iam_admin_registers_or_cancels(ctx):
    c, h, db, ids = ctx
    editor = bearer_for(EDITOR_USER)
    assert c.post(f"/api/units/{ids['SD-AF']}/subrogations", json=body(), headers=editor).status_code == 403
    assert c.post(f"/api/units/{ids['SD-AF']}/subrogations", json=body()).status_code == 401
    created = post(c, h, ids["SD-AF"]).json()["_id"]
    assert c.post(f"/api/units/subrogations/{created}/cancel", headers=editor).status_code == 403
    assert db.subrogations.docs[0]["cancelled_at"] is None


def test_BE49_a_subrogation_grants_no_permission(ctx):
    c, h, db, ids = ctx
    post(c, h, ids["SD-AF"], user=SUB_TI, ends=NOW + timedelta(days=5))
    sub = next(d for d in db.users.docs if str(d["_id"]) == SUB_TI)
    assert sub["access"] == []                                                                  # nada cambió en sus accesos
    assert c.get("/api/users", headers=bearer_for(_user(SUB_TI, "subti@slepllanquihue.cl", "Sara", "TI", []))).status_code == 403
    assert c.get("/api/establishments", headers=bearer_for(_user(SUB_TI, "subti@slepllanquihue.cl", "Sara", "TI", []))).status_code == 403


def test_BE49_creation_and_cancellation_are_audited(ctx):
    c, h, db, ids = ctx
    sid = post(c, h, ids["SD-AF"]).json()["_id"]
    c.post(f"/api/units/subrogations/{sid}/cancel", headers=h)
    acts = [(d["action"], d["target_type"], d["target_id"]) for d in db.audit_log.docs if d["action"].startswith("subrogation")]
    assert acts == [("subrogation.create", "subrogation", sid), ("subrogation.cancel", "subrogation", sid)]


# ── acting ────────────────────────────────────────────────────────────────────
def test_BE49_users_acting_filter(ctx):
    c, h, db, ids = ctx
    post(c, h, ids["SD-AF"], user=SUB_TI)                                                          # vigente
    post(c, h, ids["AF-FIN"], user=SUB_FIN, starts=NOW + timedelta(days=20))                       # futura
    post(c, h, ids["AF-CL"], user=SUB_TI, starts=NOW - timedelta(days=100), ends=NOW - timedelta(days=90))     # ya terminó
    acting = c.get("/api/users?acting=true", headers=h).json()
    assert [u["_id"] for u in acting["items"]] == [SUB_TI] and acting["total"] == 1
    assert c.get("/api/users?acting=false", headers=h).json()["total"] == len(db.users.docs)
    first = db.subrogations.docs[0]["_id"]
    c.post(f"/api/units/subrogations/{first}/cancel", headers=h)
    assert c.get("/api/users?acting=true", headers=h).json()["total"] == 0


# ── contrapartes ──────────────────────────────────────────────────────────────
def counterpart(**kw):
    return {"rbd": "7722", "role": "TI", "origin": "SLEP", "name": "Carlos TI", "email": "ti@slepllanquihue.cl", "phone": "", **kw}


def test_BE49_counterpart_user_id_is_optional_and_validated(ctx):
    c, h, db, ids = ctx
    plain = c.post("/api/counterparts", json=counterpart(), headers=h)
    assert plain.status_code == 201 and plain.json()["user_id"] is None
    linked = c.post("/api/counterparts", json=counterpart(user_id=SUB_TI), headers=h)
    assert linked.status_code == 201 and linked.json()["user_id"] == SUB_TI
    bad = c.post("/api/counterparts", json=counterpart(user_id="6600000000000000000000fe"), headers=h)
    assert bad.status_code == 422 and bad.json()["detail"][0] == {"field": "user_id", "code": "user_not_found", "message": "El usuario indicado no existe"}
    assert c.post("/api/counterparts", json=counterpart(user_id="corto"), headers=h).status_code == 422
    assert c.post("/api/counterparts", json=counterpart(user_id={"$ne": None}), headers=h).status_code == 422
    assert len(db.counterparts.docs) == 2


def test_BE49_counterpart_update_links_and_unlinks(ctx):
    c, h, db, ids = ctx
    cid = c.post("/api/counterparts", json=counterpart(), headers=h).json()["_id"]
    up = c.put(f"/api/counterparts/{cid}", json={"user_id": SUB_TI}, headers=h)
    assert up.status_code == 200 and up.json()["user_id"] == SUB_TI
    assert c.put(f"/api/counterparts/{cid}", json={"name": "Otro nombre"}, headers=h).json()["user_id"] == SUB_TI   # omitido: se conserva
    assert c.put(f"/api/counterparts/{cid}", json={"user_id": "6600000000000000000000fe"}, headers=h).status_code == 422
    assert c.put(f"/api/counterparts/{cid}", json={"user_id": ""}, headers=h).json()["user_id"] is None             # "" desvincula


# ── backfill ──────────────────────────────────────────────────────────────────
def test_BE49_backfill_plan_matches_by_normalized_email_and_never_writes(ctx):
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("backfill", Path(__file__).resolve().parents[1] / "scripts" / "backfill_counterpart_users.py")
    backfill = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backfill)
    c, h, db, ids = ctx
    db.counterparts.seed(
        {"_id": "c1", "rbd": "1", "email": "  SUBTI@SLEPLLANQUIHUE.CL ", "name": "a"},     # coincide (normalizado)
        {"_id": "c2", "rbd": "1", "email": "nadie@slepllanquihue.cl", "name": "b"},          # sin usuario
        {"_id": "c3", "rbd": "1", "email": "", "name": "c"},                                  # sin correo
        {"_id": "c4", "rbd": "1", "email": "subfin@slepllanquihue.cl", "user_id": "x", "name": "d"},   # ya vinculada
    )
    before = [dict(d) for d in db.counterparts.docs]
    plan = run(backfill.plan(db))
    assert [c for c, _ in plan["link"]] == ["c1"] and str(plan["link"][0][1]) == SUB_TI
    assert plan["no_match"] == ["c2"] and plan["no_email"] == ["c3"] and plan["already_linked"] == ["c4"]
    assert [dict(d) for d in db.counterparts.docs] == before                                       # planear no escribe
    assert [c for c, _ in run(backfill.plan(db, overwrite=True))["link"]] == ["c1", "c4"]
    src = (Path(__file__).resolve().parents[1] / "scripts" / "backfill_counterpart_users.py").read_text(encoding="utf-8")
    assert "--apply" in src and "if not apply:" in src                                            # ensayo por defecto
