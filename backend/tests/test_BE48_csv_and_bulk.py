"""
test_BE48_csv_and_bulk.py
━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: US-30..US-36 · CSV con vista previa, alta masiva parcial y operaciones masivas (E5, R5, R6)

Verifica que:
  - la plantilla la sirve el servidor (UTF-8 con BOM, `;`) y vuelve a importarse sin errores
  - el CSV se traduce a JSON con la biblioteca estándar: utf-8-sig o cp1252, `;` o `,`, y NO escribe nada
  - cada fila trae su `data` (un ítem de bulk-create) y sus errores; los errores de archivo dan 422/413
  - bulk-create es parcial (los inválidos no frenan al resto), tiene dry_run y envía las invitaciones DESPUÉS de responder
  - bulk aplica una sola operación a hasta 200 usuarios con resultado por ítem y las invariantes de admin
  - todo es solo de iam/admin y todo lote comparte un bulk_id en la auditoría
"""
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.mail.mail_service import MailError
from tests.conftest import ADMIN_USER, EDITOR_USER, VIEWER_USER, _user, bearer_for, prepare_org

HEADER = "email;first_name;last_name;personal_phone;work_extension;unit_code;rbd;positions"
OTHER_ADMIN = _user("6600000000000000000000a9", "otro.admin@slepllanquihue.cl", "Otro", "Admin", [("iam", "admin")])
SCHOOL_USER = _user("6600000000000000000000b9", "docente@slepllanquihue.cl", "Dora", "Docente", [("datos", "viewer")],
                    is_slep_staff=False, unit_id=None, rbd="7722", positions=["DOCENTE"])


@pytest.fixture
def ctx(fake_db, mailbox):
    ids = prepare_org(fake_db, ADMIN_USER, EDITOR_USER, VIEWER_USER, OTHER_ADMIN, SCHOOL_USER)
    fake_db.establishments.seed({"_id": "est1", "rbd": "7722", "name": "Liceo"}, {"_id": "est2", "rbd": "7801", "name": "Escuela"})
    from app.main import app
    return TestClient(app, raise_server_exceptions=True), bearer_for(ADMIN_USER), fake_db, ids, mailbox


def upload(c, h, content, encoding="utf-8", name="usuarios.csv"):
    data = content if isinstance(content, bytes) else content.encode(encoding)
    return c.post("/api/users/import", files={"file": (name, data, "text/csv")}, headers=h)


def rows_of(r):
    assert r.status_code == 200, r.text
    return r.json()["rows"]


def codes(row):
    return {e["code"] for e in row["errors"]}


def item(i, ids, **kw):
    return {"email": f"nuevo{i}@slepllanquihue.cl", "first_name": f"Nombre{i}", "last_name": "Apellido",
            "is_slep_staff": True, "unit_id": ids["AF-TI"], **kw}


# ══ Plantilla ═════════════════════════════════════════════════════════════════════════════
def test_BE48_template_is_served_with_bom_and_round_trips(ctx):
    c, h, db, ids, box = ctx
    r = c.get("/api/users/import/template", headers=h)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert 'attachment; filename="plantilla-usuarios.csv"' == r.headers["content-disposition"]
    assert r.content.startswith(b"\xef\xbb\xbf") and r.content[3:].decode().splitlines()[0] == HEADER
    again = upload(c, h, r.content)                                       # el archivo descargado se importa tal cual
    body = again.json()
    assert again.status_code == 200 and body["total"] == 2 and body["valid"] == 2 and body["invalid"] == 0


def test_BE48_template_and_import_are_iam_admin_only(ctx):
    c, h, db, ids, box = ctx
    for call in (lambda hh: c.get("/api/users/import/template", headers=hh),
                 lambda hh: upload(c, hh, HEADER + "\n"),
                 lambda hh: c.post("/api/users/bulk-create", json={"items": [{}]}, headers=hh),
                 lambda hh: c.post("/api/users/bulk", json={"user_ids": ["x"], "operation": {"op": "disable"}}, headers=hh)):
        assert call({}).status_code == 401
        assert call(bearer_for(EDITOR_USER)).status_code == 403


# ══ CSV: lectura ══════════════════════════════════════════════════════════════════════════
def test_BE48_import_translates_rows_and_writes_nothing(ctx):
    c, h, db, ids, box = ctx
    csv_text = (HEADER + "\n"
                "ana.perez@slepllanquihue.cl;Ana;Pérez;+56912345678;4521;AF-TI;;\n"
                "luis.soto@slepllanquihue.cl;Luis;Soto;;;;7722;DOCENTE|PIE_ENCARGADO\n")
    users_before, audit_before = len(db.users.docs), len(db.audit_log.docs)
    r = upload(c, h, csv_text)
    body = r.json()
    assert body["total"] == 2 and body["valid"] == 2 and body["invalid"] == 0
    first, second = body["rows"]
    assert first["row"] == 2 and second["row"] == 3                          # la cabecera es la fila 1
    assert first["data"] == {"email": "ana.perez@slepllanquihue.cl", "first_name": "Ana", "last_name": "Pérez",
                             "personal_phone": "+56912345678", "work_extension": "4521", "is_slep_staff": True,
                             "unit_id": ids["AF-TI"], "rbd": None, "positions": []}
    assert second["data"]["is_slep_staff"] is False and second["data"]["rbd"] == "7722" and second["data"]["unit_id"] is None
    assert second["data"]["positions"] == ["DOCENTE", "PIE_ENCARGADO"]
    assert (len(db.users.docs), len(db.audit_log.docs), box.messages) == (users_before, audit_before, [])
    # la vista previa es exactamente el body de bulk-create
    created = c.post("/api/users/bulk-create", json={"items": [x["data"] for x in body["rows"]]}, headers=h).json()
    assert [i["status"] for i in created["items"]] == ["created", "created"]


@pytest.mark.parametrize("encoding,delimiter,bom", [("utf-8", ";", True), ("utf-8", ",", False), ("cp1252", ";", False), ("cp1252", ",", False)])
def test_BE48_accepts_utf8_bom_and_cp1252_with_either_delimiter(ctx, encoding, delimiter, bom):
    c, h, db, ids, box = ctx
    text = (HEADER.replace(";", delimiter) + "\n" + delimiter.join(["ñandú.pérez@slepllanquihue.cl", "Ñandú", "Pérez", "", "", "AF-TI", "", ""]) + "\n")
    # el correo con acentos no es válido: lo que se comprueba aquí es la DECODIFICACIÓN del nombre
    raw = (b"\xef\xbb\xbf" if bom else b"") + text.encode(encoding)
    data = rows_of(upload(c, h, raw))[0]["data"]
    assert data["first_name"] == "Ñandú" and data["last_name"] == "Pérez" and data["unit_id"] == ids["AF-TI"]


def test_BE48_headers_are_case_and_space_insensitive_and_blank_rows_are_skipped(ctx):
    c, h, db, ids, box = ctx
    text = " Email ;FIRST_NAME; Last_Name ;Unit_Code\n\nana@slepllanquihue.cl;Ana;Pérez;af-ti\n;;;\nbeto@slepllanquihue.cl;Beto;Ríos;AF-TI\n"
    rows = rows_of(upload(c, h, text))
    assert [r["row"] for r in rows] == [3, 5]                                 # los números respetan las filas vacías
    assert all(not r["errors"] and r["data"]["unit_id"] == ids["AF-TI"] for r in rows)


def test_BE48_row_errors_are_reported_per_row_with_stable_codes(ctx):
    c, h, db, ids, box = ctx
    text = (HEADER + "\n"
            "ok@slepllanquihue.cl;Ok;Ok;;;AF-TI;;\n"                                   # 2 válida
            "malo@gmail.com;Mal;Dominio;;;AF-TI;;\n"                                   # 3 dominio
            "uno@slepllanquihue.cl;Uno;Dos;;;NO-EXISTE;;\n"                            # 4 unidad
            "dos@slepllanquihue.cl;Dos;Tres;;;AF-TI;7722;\n"                           # 5 ambos
            "tres@slepllanquihue.cl;Tres;Cuatro;;;;;\n"                                # 6 ninguno
            "ok@slepllanquihue.cl;Rep;Etida;;;AF-TI;;\n"                               # 7 repetido en el archivo
            f"{EDITOR_USER['email']};Ya;Existe;;;AF-TI;;\n"                            # 8 ya existe en la base
            "tel@slepllanquihue.cl;Te;Le;12345;;AF-TI;;\n"                             # 9 teléfono
            "pos@slepllanquihue.cl;Po;Sicion;;;;7722;ASTRONAUTA\n"                     # 10 cargo
            "rbd@slepllanquihue.cl;Rb;D;;;;99999;DOCENTE\n"                            # 11 rbd inexistente
            "col@slepllanquihue.cl;Co;L;;;AF-TI;;;extra\n")                            # 12 celdas de más
    body = upload(c, h, text).json()
    rows = {r["row"]: r for r in body["rows"]}
    assert not rows[2]["errors"]
    assert "email" in {e["field"] for e in rows[3]["errors"]}
    assert codes(rows[4]) == {"unit_not_found"} and rows[4]["errors"][0]["field"] == "unit_code"
    assert codes(rows[5]) == {"invalid_combination"} and codes(rows[6]) == {"invalid_combination"}
    assert codes(rows[7]) == {"duplicate_in_batch"} and rows[7]["errors"][0]["message"].endswith("en la fila 2")   # fila del ARCHIVO
    assert codes(rows[8]) == {"duplicate"}
    assert "personal_phone" in {e["field"] for e in rows[9]["errors"]}
    assert any(e["field"].startswith("positions") for e in rows[10]["errors"])        # "positions.0": el índice del cargo
    assert codes(rows[11]) == {"rbd_not_found"}
    assert "too_many_columns" in codes(rows[12])
    assert body["valid"] == 1 and body["invalid"] == 10 and body["total"] == 11


@pytest.mark.parametrize("content,code", [
    (b"", "empty_file"), (b"   \n \n", "empty_file"), (HEADER + "\n", "empty_file"),
    ("email;first_name;last_name;sorpresa\na@slepllanquihue.cl;A;B;x\n", "unknown_columns"),
    ("email;first_name\na@slepllanquihue.cl;A\n", "missing_columns"),
    ("email;email;first_name;last_name\na@slepllanquihue.cl;a@slepllanquihue.cl;A;B\n", "duplicate_columns"),
    (b"email;first_name;last_name\n\x00\x01\x02binario\n", "not_csv"),
    (b"\x89PNG\r\n\x1a\n\x00\x00\x00", "not_csv"),
    (b"email;first_name;last_name\n\x81\x8d\x8f\x90;a;b\n", "bad_encoding"),
])
def test_BE48_file_level_errors_are_422_with_a_code(ctx, content, code):
    c, h, db, ids, box = ctx
    r = upload(c, h, content)
    assert r.status_code == 422 and r.json()["detail"][0]["code"] == code


def test_BE48_size_and_row_limits(ctx):
    c, h, db, ids, box = ctx
    big = upload(c, h, b"email;first_name;last_name\n" + b"a" * (1024 * 1024 + 1))
    assert big.status_code == 413 and big.json()["detail"]["code"] == "file_too_large"
    lines = "\n".join(f"u{i}@slepllanquihue.cl;N{i};A;;;AF-TI;;" for i in range(201))
    over = upload(c, h, HEADER + "\n" + lines + "\n")
    assert over.status_code == 422 and over.json()["detail"][0]["code"] == "too_many_rows"
    exactly = upload(c, h, HEADER + "\n" + "\n".join(f"u{i}@slepllanquihue.cl;N{i};A;;;AF-TI;;" for i in range(200)) + "\n")
    assert exactly.status_code == 200 and exactly.json()["valid"] == 200


def test_BE48_missing_file_part_is_422_and_hostile_cells_stay_plain_text(ctx):
    c, h, db, ids, box = ctx
    assert c.post("/api/users/import", headers=h).status_code == 422
    assert c.post("/api/users/import", data={"file": "texto"}, headers=h).status_code == 422
    text = HEADER + '\n{"$ne": null};{"$gt": ""};$where;;;AF-TI;;\n'
    rows = rows_of(upload(c, h, text))
    assert rows[0]["errors"] and rows[0]["data"]["email"] == '{"$ne": null}'      # texto, nunca un operador


# ══ bulk-create ═══════════════════════════════════════════════════════════════════════════
def test_BE48_bulk_create_is_partial_and_invites_after_responding(ctx):
    c, h, db, ids, box = ctx
    items = [item(1, ids), item(2, ids, email="no-es-un-correo"), item(3, ids, email=item(1, ids)["email"])]
    r = c.post("/api/users/bulk-create", json={"items": items}, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert [i["status"] for i in body["items"]] == ["created", "invalid", "duplicate"]
    assert (body["total"], body["created"], body["succeeded"], body["failed"], body["dry_run"]) == (3, 1, 1, 2, False)
    assert body["items"][0]["invitation"] == "queued" and body["items"][1]["invitation"] is None
    assert [i["index"] for i in body["items"]] == [0, 1, 2]
    assert len([d for d in db.users.docs if d["email"].startswith("nuevo")]) == 1
    # el TestClient ejecuta las tareas en segundo plano antes de devolver: el correo ya salió
    assert [m["to"] for m in box.messages] == ["nuevo1@slepllanquihue.cl"]
    stored = next(d for d in db.users.docs if d["email"] == "nuevo1@slepllanquihue.cl")
    assert stored["status"] == "invited" and stored["invitation"]["last_error"] is None and stored["invitation"]["sent_at"]
    # un único bulk_id agrupa las altas y las invitaciones en la auditoría
    audited = [d for d in db.audit_log.docs if d["action"] in ("user.create", "user.invite")]
    assert {d["bulk_id"] for d in audited} == {body["bulk_id"]} and {d["action"] for d in audited} == {"user.create", "user.invite"}


def test_BE48_bulk_create_dry_run_writes_nothing(ctx):
    c, h, db, ids, box = ctx
    n_users, n_audit = len(db.users.docs), len(db.audit_log.docs)
    body = c.post("/api/users/bulk-create", json={"items": [item(1, ids), item(2, ids, email="x")], "dry_run": True}, headers=h).json()
    assert [i["status"] for i in body["items"]] == ["ok", "invalid"] and body["dry_run"] is True
    assert all(i["invitation"] is None for i in body["items"])
    assert (len(db.users.docs), len(db.audit_log.docs), box.messages) == (n_users, n_audit, [])


def test_BE48_bulk_create_mail_failures_do_not_affect_the_response_or_other_users(ctx):
    c, h, db, ids, box = ctx
    box.fail_with = MailError("mail_send_failed")
    body = c.post("/api/users/bulk-create", json={"items": [item(1, ids), item(2, ids)]}, headers=h).json()
    assert [i["status"] for i in body["items"]] == ["created", "created"]
    for d in (d for d in db.users.docs if d["email"].startswith("nuevo")):
        assert d["status"] == "invited" and d["invitation"]["last_error"] == "mail_send_failed" and d["invitation"]["sent_at"] is None


def test_BE48_bulk_create_survives_a_crash_in_the_background_job(ctx, caplog):
    c, h, db, ids, box = ctx
    with patch("app.auth.auth_service.AuthService.invite_many", AsyncMock(side_effect=RuntimeError("boom"))):
        r = c.post("/api/users/bulk-create", json={"items": [item(1, ids)]}, headers=h)
    assert r.status_code == 200 and r.json()["items"][0]["status"] == "created"
    assert "Falló el envío en segundo plano" in caplog.text


def test_BE48_bulk_create_limits_and_strict_input(ctx):
    c, h, db, ids, box = ctx
    post = lambda body: c.post("/api/users/bulk-create", json=body, headers=h)
    assert post({"items": []}).status_code == 422
    assert post({"items": [item(i, ids) for i in range(201)]}).status_code == 422
    assert post({"items": [item(i, ids) for i in range(200)], "dry_run": True}).status_code == 200
    assert post({"items": [item(1, ids)], "role": "admin"}).status_code == 422
    assert post({"items": "no-es-una-lista"}).status_code == 422
    assert post({"items": [item(1, ids, role="admin", status="active", access=[{"platform_id": "iam", "role": "admin"}])]}).json()["items"][0]["status"] == "invalid"
    assert post({"items": [{"email": {"$ne": None}, "first_name": {"$gt": ""}}]}).json()["items"][0]["status"] == "invalid"
    assert not [d for d in db.users.docs if d.get("access") and d["email"].startswith("nuevo") and d["access"]]


def test_BE48_bulk_created_users_start_as_datos_viewer_and_without_a_credential(ctx):
    c, h, db, ids, box = ctx
    c.post("/api/users/bulk-create", json={"items": [item(1, ids)]}, headers=h)
    doc = next(d for d in db.users.docs if d["email"] == "nuevo1@slepllanquihue.cl")
    assert [(a["platform_id"], a["role"]) for a in doc["access"]] == [("datos", "viewer")]   # C26
    assert doc["auth_providers"] == []


# ══ bulk: operaciones ═════════════════════════════════════════════════════════════════════
def bulk(c, h, ids, op, **extra):
    return c.post("/api/users/bulk", json={"user_ids": ids, "operation": op, **extra}, headers=h)


def status_of(db, uid):
    return next(d for d in db.users.docs if str(d["_id"]) == uid)


def test_BE48_assign_unit_reports_each_user_and_flags_school_users(ctx):
    c, h, db, ids, box = ctx
    r = bulk(c, h, [EDITOR_USER["_id"], SCHOOL_USER["_id"], "6600000000000000000000ff", "no-es-un-id", VIEWER_USER["_id"]],
             {"op": "assign_unit", "unit_id": ids["AF-FIN"]})
    body = r.json()
    assert [i["status"] for i in body["items"]] == ["ok", "mode_mismatch", "not_found", "not_found", "ok"]
    assert (body["total"], body["succeeded"], body["failed"], body["created"]) == (5, 2, 3, 0)
    assert str(status_of(db, EDITOR_USER["_id"])["unit_id"]) == ids["AF-FIN"] and status_of(db, SCHOOL_USER["_id"])["unit_id"] is None
    assert body["items"][1]["errors"][0]["code"] == "invalid_combination"
    audited = [d for d in db.audit_log.docs if d["bulk_id"] == body["bulk_id"]]
    assert len(audited) == 2 and {d["action"] for d in audited} == {"user.update"}


def test_BE48_operation_level_errors_fail_the_whole_request_before_touching_anyone(ctx):
    c, h, db, ids, box = ctx
    def state():           # la actividad de la sesión del admin cambia en cada petición, por diseño
        return json.dumps([{k: v for k, v in d.items() if k != "last_activity_at"} for d in db.users.docs], default=str)
    snapshot = state()
    assert bulk(c, h, [EDITOR_USER["_id"]], {"op": "grant_access", "platform_id": "no-existe", "role": "admin"}).status_code == 404
    assert bulk(c, h, [EDITOR_USER["_id"]], {"op": "grant_access", "platform_id": "iam", "role": "editor"}).json()["detail"][0]["code"] == "invalid_role"
    assert bulk(c, h, [EDITOR_USER["_id"]], {"op": "revoke_access", "platform_id": "no-existe"}).status_code == 404
    inactive = next(d for d in db.units.docs if str(d["_id"]) == ids["AF-FIN"])
    inactive["status"] = "inactive"
    r = bulk(c, h, [EDITOR_USER["_id"]], {"op": "assign_unit", "unit_id": ids["AF-FIN"]})
    assert r.status_code == 422 and r.json()["detail"][0]["code"] == "unit_not_found"
    assert state() == snapshot


def test_BE48_grant_and_revoke_access(ctx):
    c, h, db, ids, box = ctx
    body = bulk(c, h, [VIEWER_USER["_id"], SCHOOL_USER["_id"]], {"op": "grant_access", "platform_id": "selloverde", "role": "editor"}).json()
    assert [i["status"] for i in body["items"]] == ["ok", "ok"]
    for uid in (VIEWER_USER["_id"], SCHOOL_USER["_id"]):
        assert {a["platform_id"]: a["role"] for a in status_of(db, uid)["access"]}["selloverde"] == "editor"
    grants = [d for d in db.audit_log.docs if d["bulk_id"] == body["bulk_id"]]
    assert {d["action"] for d in grants} == {"access.grant"} and len(grants) == 2
    body = bulk(c, h, [VIEWER_USER["_id"], EDITOR_USER["_id"]], {"op": "revoke_access", "platform_id": "selloverde"}).json()
    assert [i["status"] for i in body["items"]] == ["ok", "ok"]                     # quitar lo que no tenía no es un error
    assert "selloverde" not in {a["platform_id"] for a in status_of(db, VIEWER_USER["_id"])["access"]}
    assert len([d for d in db.audit_log.docs if d["bulk_id"] == body["bulk_id"]]) == 1   # solo lo que cambió de verdad


def test_BE48_disable_enable_and_the_self_invariant(ctx):
    c, h, db, ids, box = ctx
    body = bulk(c, h, [EDITOR_USER["_id"], ADMIN_USER["_id"], VIEWER_USER["_id"]], {"op": "disable"}).json()
    assert [i["status"] for i in body["items"]] == ["ok", "self", "ok"]
    assert status_of(db, ADMIN_USER["_id"])["status"] == "active"
    assert [status_of(db, u)["status"] for u in (EDITOR_USER["_id"], VIEWER_USER["_id"])] == ["disabled", "disabled"]
    again = bulk(c, h, [EDITOR_USER["_id"]], {"op": "disable"}).json()
    assert again["items"][0]["status"] == "ok"                                       # ya estaba desactivado: no-op
    back = bulk(c, h, [EDITOR_USER["_id"], VIEWER_USER["_id"]], {"op": "enable"}).json()
    assert [i["status"] for i in back["items"]] == ["ok", "ok"]
    assert status_of(db, EDITOR_USER["_id"])["status"] == "active"


def test_BE48_the_last_global_admin_cannot_be_removed_even_inside_a_batch(ctx):
    c, h, db, ids, box = ctx
    # Hay dos admins globales: el batch intenta quitar iam a ambos. Va en el orden recibido:
    # el primero sale (queda otro), el segundo sería el último y se rechaza.
    body = bulk(c, h, [OTHER_ADMIN["_id"], ADMIN_USER["_id"]], {"op": "revoke_access", "platform_id": "iam"}).json()
    assert [i["status"] for i in body["items"]] == ["ok", "last_admin"]
    assert body["items"][1]["errors"][0]["code"] == "last_admin"
    admins = [d for d in db.users.docs if d["status"] == "active" and any(a["platform_id"] == "iam" and a["role"] == "admin" for a in d["access"])]
    assert [str(d["_id"]) for d in admins] == [ADMIN_USER["_id"]]
    # y con un único admin, ni siquiera una desactivación masiva que lo incluya lo toca
    assert bulk(c, h, [ADMIN_USER["_id"]], {"op": "disable"}).json()["items"][0]["status"] == "self"


@pytest.mark.parametrize("order", [(ADMIN_USER["_id"], OTHER_ADMIN["_id"]), (OTHER_ADMIN["_id"], ADMIN_USER["_id"])])
def test_BE48_there_is_always_an_active_admin_whatever_the_order(ctx, order):
    c, h, db, ids, box = ctx
    # Solo se toca la base en memoria de este test: los fixtures de módulo son compartidos y no se mutan.
    body = bulk(c, h, list(order), {"op": "revoke_access", "platform_id": "iam"}).json()
    assert [i["status"] for i in body["items"]] == ["ok", "last_admin"]
    left = [d for d in db.users.docs if d["status"] == "active" and any(a["platform_id"] == "iam" and a["role"] == "admin" for a in d["access"])]
    assert [str(d["_id"]) for d in left] == [order[1]]


def test_BE48_bulk_request_validation(ctx):
    c, h, db, ids, box = ctx
    base = {"op": "disable"}
    assert bulk(c, h, [], base).status_code == 422
    assert bulk(c, h, [f"{i:024d}" for i in range(201)], base).status_code == 422
    assert bulk(c, h, [f"{i:024d}" for i in range(200)], base).status_code == 200
    assert bulk(c, h, [EDITOR_USER["_id"], EDITOR_USER["_id"]], base).status_code == 422          # repetidos
    assert bulk(c, h, ["x" * 65], base).status_code == 422
    assert bulk(c, h, [EDITOR_USER["_id"]], {"op": "borrar_todo"}).status_code == 422
    assert bulk(c, h, [EDITOR_USER["_id"]], {"op": "disable", "role": "admin"}).status_code == 422
    assert bulk(c, h, [EDITOR_USER["_id"]], {"op": "assign_unit", "unit_id": "corto"}).status_code == 422
    assert bulk(c, h, [EDITOR_USER["_id"]], {"op": "grant_access", "platform_id": "datos"}).status_code == 422
    assert bulk(c, h, [{"$ne": None}], base).status_code == 422
    assert c.post("/api/users/bulk", json={"user_ids": [EDITOR_USER["_id"]], "operation": base, "extra": 1}, headers=h).status_code == 422
