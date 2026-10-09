"""
test_BE46_first_access_links.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: US-14, US-15, US-16 · Invitación, reenvío, restablecimiento y canje del enlace (ADR-012)

Verifica que:
  - el alta envía un correo con un enlace cuyo token va en el FRAGMENTO, armado con PUBLIC_BASE_URL (no con el Host)
  - en la base solo está el sha256; el token no aparece en la base, el audit ni los logs
  - un fallo de correo no revierte el alta (201, `invited`, last_error) y el reenvío lo recupera
  - reenviar invalida el enlace anterior; un solo documento por (usuario, propósito)
  - el canje define la contraseña, activa al usuario y es de un solo uso
  - usado, vencido, inexistente, de un usuario desactivado o de otro estado dan EXACTAMENTE la misma respuesta
  - una contraseña que incumple la política da 422 y NO consume el enlace
  - restablecer cierra las sesiones abiertas; el admin nunca ve ni define la contraseña
  - las rutas de envío son solo de iam/admin y el correo sale solo con datos del documento del usuario
"""
import hashlib
import json
import logging
import time
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.mail.mail_service import MailError
from tests.conftest import (ADMIN_USER, EDITOR_USER, bearer_for, prepare_org, run, user_with_password)

GOOD_PASSWORD = "una-contrasena-larga-y-unica-77"
NEW_USER = {"first_name": "Ana", "last_name": "Pérez", "email": "ana.perez@slepllanquihue.cl", "is_slep_staff": True}
GENERIC = {"code": "invalid_or_expired_link",
           "message": "El enlace no es válido o ya venció. Pide a un administrador que te envíe uno nuevo."}


@pytest.fixture
def ctx(fake_db, mailbox):
    ids = prepare_org(fake_db, ADMIN_USER, user_with_password(EDITOR_USER, "contrasena-anterior-muy-larga-1"))
    from app.main import app
    return TestClient(app, raise_server_exceptions=True), bearer_for(ADMIN_USER), fake_db, ids, mailbox


def create(c, h, ids, **kw):
    r = c.post("/api/users", json={**NEW_USER, "unit_id": ids["AF-TI"], **kw}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def uid(body):
    return body.get("_id") or body["id"]


def redeem(c, token, password=GOOD_PASSWORD):
    return c.post("/api/auth/set-password", json={"token": token, "password": password})


def token_docs(db, **match):
    return [d for d in db.auth_tokens.docs if all(d.get(k) == v for k, v in match.items())]


# ── alta e invitación ─────────────────────────────────────────────────────────
def test_BE46_create_sends_one_email_with_fragment_link(ctx):
    c, h, db, ids, box = ctx
    body = create(c, h, ids)
    assert len(box.messages) == 1
    msg = box.messages[0]
    assert msg["to"] == "ana.perez@slepllanquihue.cl" and "contraseña" in msg["subject"]
    token = box.last_token()
    link = f"{settings.PUBLIC_BASE_URL}/definir-contrasena#token={token}"
    assert link in msg["text"] and link in msg["html"]
    assert "?token=" not in msg["text"] and "token=" not in msg["text"].replace("#token=", "")      # solo en el fragmento
    inv = body["invitation"]
    assert inv["sent"] is True and inv["last_error"] is None and inv["sent_at"] and inv["expires_at"]
    assert body["status"] == "invited"


def test_BE46_link_uses_public_base_url_not_the_request_host(ctx):
    c, h, db, ids, box = ctx
    r = c.post("/api/users", json={**NEW_USER, "unit_id": ids["AF-TI"]}, headers={**h, "Host": "evil.example.com", "X-Forwarded-Host": "evil.example.com"})
    assert r.status_code == 201
    assert "evil.example.com" not in box.messages[0]["text"] + box.messages[0]["html"]
    assert settings.PUBLIC_BASE_URL in box.messages[0]["text"]


def test_BE46_only_the_hash_is_stored_and_the_token_never_leaks(ctx, caplog):
    c, h, db, ids, box = ctx
    with caplog.at_level(logging.DEBUG):
        body = create(c, h, ids)
        token = box.last_token()
        redeem(c, token)
    (doc,) = token_docs(db, purpose="invite")
    assert doc["token_hash"] == hashlib.sha256(token.encode()).hexdigest() and doc["token_hash"] != token
    dump = json.dumps({"db": [d for col in db._cols.values() for d in col.docs], "audit": db.audit_log.docs}, default=str)
    assert token not in dump
    assert token not in caplog.text and GOOD_PASSWORD not in caplog.text and GOOD_PASSWORD not in dump


def test_BE46_invite_lasts_72_hours(ctx):
    c, h, db, ids, box = ctx
    create(c, h, ids)
    (doc,) = token_docs(db, purpose="invite")
    delta = doc["expires_at"] - datetime.now(timezone.utc).replace(tzinfo=None)
    assert timedelta(hours=71, minutes=59) < delta <= timedelta(hours=72)


def test_BE46_mail_failure_does_not_revert_the_signup(ctx):
    c, h, db, ids, box = ctx
    box.fail_with = MailError("mail_send_failed")
    r = c.post("/api/users", json={**NEW_USER, "unit_id": ids["AF-TI"]}, headers=h)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "invited"
    assert body["invitation"]["sent"] is False and body["invitation"]["last_error"] == "mail_send_failed"
    assert body["invitation"]["expires_at"] is None
    assert [d for d in db.users.docs if d["email"] == NEW_USER["email"]]
    # el motivo queda en el audit, sin el token
    assert [d for d in db.audit_log.docs if d["action"] == "user.invite"][-1]["changes"] == {"invitation": [None, "mail_send_failed"]}


def test_BE46_unexpected_mail_exception_is_also_contained(ctx):
    c, h, db, ids, box = ctx
    box.fail_with = RuntimeError("boom")
    r = c.post("/api/users", json={**NEW_USER, "unit_id": ids["AF-TI"]}, headers=h)
    assert r.status_code == 201 and r.json()["invitation"]["last_error"] == "mail_send_failed"


# ── reenvío ───────────────────────────────────────────────────────────────────
def test_BE46_resend_recovers_a_failed_invitation(ctx):
    c, h, db, ids, box = ctx
    box.fail_with = MailError("mail_auth_failed")
    body = create(c, h, ids)
    assert body["invitation"]["last_error"] == "mail_auth_failed"
    box.fail_with = None
    r = c.post(f"/api/users/{uid(body)}/invitation", headers=h)
    assert r.status_code == 200
    assert r.json()["invitation"]["sent"] is True and r.json()["invitation"]["last_error"] is None
    assert len(box.messages) == 1


def test_BE46_resend_invalidates_the_previous_link_and_keeps_one_document(ctx):
    c, h, db, ids, box = ctx
    body = create(c, h, ids)
    first = box.last_token()
    assert c.post(f"/api/users/{uid(body)}/invitation", headers=h).status_code == 200
    second = box.last_token()
    assert first != second and len(token_docs(db, purpose="invite")) == 1
    assert redeem(c, first).status_code == 400
    assert redeem(c, second).status_code == 204


def test_BE46_resend_only_for_invited_users(ctx):
    c, h, db, ids, box = ctx
    # activo
    r = c.post(f"/api/users/{EDITOR_USER['_id']}/invitation", headers=h)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "not_invited"
    # desactivado
    body = create(c, h, ids)
    c.post(f"/api/users/{uid(body)}/disable", headers=h)
    assert c.post(f"/api/users/{uid(body)}/invitation", headers=h).status_code == 409
    assert c.post("/api/users/6600000000000000000000ff/invitation", headers=h).status_code == 404
    assert c.post("/api/users/no-es-un-id/invitation", headers=h).status_code == 404


# ── canje ─────────────────────────────────────────────────────────────────────
def test_BE46_redeem_defines_password_activates_user_and_allows_login(ctx):
    c, h, db, ids, box = ctx
    body = create(c, h, ids)
    login = lambda pw: c.post("/api/auth/login", json={"username": NEW_USER["email"], "password": pw})
    assert login(GOOD_PASSWORD).status_code == 401                          # invitado: aún no entra
    r = redeem(c, box.last_token())
    assert r.status_code == 204 and r.content == b""
    stored = next(d for d in db.users.docs if d["email"] == NEW_USER["email"])
    provider = stored["auth_providers"][0]
    assert stored["status"] == "active" and provider["provider"] == "local" and provider["hashed_password"].startswith("$2")
    assert provider["password_changed_at"] is not None and provider["must_change_password"] is False
    assert login(GOOD_PASSWORD).status_code == 200
    assert login("otra-contrasena-cualquiera-1").status_code == 401


def test_BE46_link_is_single_use(ctx):
    c, h, db, ids, box = ctx
    create(c, h, ids)
    token = box.last_token()
    assert redeem(c, token).status_code == 204
    again = redeem(c, token, "otra-contrasena-larga-y-unica-88")
    assert again.status_code == 400 and again.json()["detail"] == GENERIC
    # la contraseña no cambió
    assert c.post("/api/auth/login", json={"username": NEW_USER["email"], "password": GOOD_PASSWORD}).status_code == 200


def test_BE46_reset_link_is_single_use(ctx):
    """El estado del usuario no puede tapar el reuso: un reset sigue valiendo `active` tras canjearlo."""
    c, h, db, ids, box = ctx
    c.post(f"/api/users/{EDITOR_USER['_id']}/password-reset", headers=h)
    token = box.last_token()
    assert redeem(c, token).status_code == 204
    again = redeem(c, token, "otra-contrasena-larga-y-unica-88")
    assert again.status_code == 400 and again.json()["detail"] == GENERIC
    assert c.post("/api/auth/login", json={"username": EDITOR_USER["email"], "password": GOOD_PASSWORD}).status_code == 200


def test_BE46_used_invite_stays_dead_even_if_the_user_is_invited_again(ctx):
    """Independiente del chequeo de estado: el token consumido nunca se puede volver a canjear."""
    c, h, db, ids, box = ctx
    create(c, h, ids)
    token = box.last_token()
    assert redeem(c, token).status_code == 204
    next(d for d in db.users.docs if d["email"] == NEW_USER["email"])["status"] = "invited"
    assert redeem(c, token, "otra-contrasena-larga-y-unica-88").status_code == 400


def test_BE46_consume_is_atomic_only_one_of_two_redemptions_wins(ctx):
    c, h, db, ids, box = ctx
    create(c, h, ids)
    token = box.last_token()
    from app.auth.auth_service import auth_service
    filt = auth_service._redeemable(token)
    from pymongo import ReturnDocument
    from app.database.database_service import db_service
    set_used = {"$set": {"used_at": datetime(2026, 1, 1)}}
    first = run(db_service.db.auth_tokens.find_one_and_update(filt, set_used, return_document=ReturnDocument.AFTER))
    second = run(db_service.db.auth_tokens.find_one_and_update(auth_service._redeemable(token), set_used, return_document=ReturnDocument.AFTER))
    assert first is not None and second is None


def test_BE46_every_link_failure_gives_the_same_response(ctx):
    c, h, db, ids, box = ctx
    responses = []
    # inexistente
    responses.append(redeem(c, "x" * 43))
    # usado
    body = create(c, h, ids)
    used = box.last_token()
    redeem(c, used)
    responses.append(redeem(c, used))
    # vencido
    other = create(c, h, ids, email="beto.rios@slepllanquihue.cl", first_name="Beto", last_name="Ríos")
    expired = box.last_token()
    token_docs(db, user_id=next(d["_id"] for d in db.users.docs if d["email"] == "beto.rios@slepllanquihue.cl"))[0]["expires_at"] = datetime(2020, 1, 1)
    responses.append(redeem(c, expired))
    # de un usuario desactivado
    third = create(c, h, ids, email="carla.soto@slepllanquihue.cl", first_name="Carla", last_name="Soto")
    disabled = box.last_token()
    c.post(f"/api/users/{uid(third)}/disable", headers=h)
    responses.append(redeem(c, disabled))
    for r in responses:
        assert r.status_code == 400 and r.json() == responses[0].json() and r.json()["detail"] == GENERIC


def test_BE46_policy_violation_is_422_and_does_not_consume_the_link(ctx):
    c, h, db, ids, box = ctx
    create(c, h, ids)
    token = box.last_token()
    short = redeem(c, token, "corta")
    assert short.status_code == 422 and short.json()["detail"][0]["code"] == "min_length"
    common = redeem(c, token, "password1234567")
    assert common.status_code == 422 and {v["code"] for v in common.json()["detail"]} & {"common_password"}
    with_email = redeem(c, token, "anaperez-es-mi-clave-123")
    assert with_email.status_code == 422 and "context_word" in {v["code"] for v in with_email.json()["detail"]}
    assert token_docs(db, purpose="invite")[0]["used_at"] is None
    assert redeem(c, token).status_code == 204                                # el mismo enlace sigue sirviendo


def test_BE46_expired_link_is_rejected(ctx):
    c, h, db, ids, box = ctx
    create(c, h, ids)
    token = box.last_token()
    token_docs(db, purpose="invite")[0]["expires_at"] = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
    assert redeem(c, token).status_code == 400


def test_BE46_invite_link_cannot_set_password_of_an_already_active_user(ctx):
    c, h, db, ids, box = ctx
    create(c, h, ids)
    token = box.last_token()
    stored = next(d for d in db.users.docs if d["email"] == NEW_USER["email"])
    stored["status"] = "active"                                              # activado por otra vía (p. ej. Google, F6)
    assert redeem(c, token).status_code == 400


def test_BE46_body_validation(ctx):
    c, h, db, ids, box = ctx
    assert c.post("/api/auth/set-password", json={"token": "corto", "password": "x"}).status_code == 422
    assert c.post("/api/auth/set-password", json={"token": {"$ne": None}, "password": "x"}).status_code == 422
    assert c.post("/api/auth/set-password", json={"token": "t" * 43}).status_code == 422
    assert c.post("/api/auth/set-password", json={"token": "t" * 43, "password": "x" * 2000}).status_code == 422


# ── restablecimiento ──────────────────────────────────────────────────────────
def test_BE46_reset_sends_link_and_the_admin_never_sees_a_password(ctx):
    c, h, db, ids, box = ctx
    r = c.post(f"/api/users/{EDITOR_USER['_id']}/password-reset", headers=h)
    assert r.status_code == 202 and r.json()["sent"] is True
    assert set(r.json()) == {"sent", "expires_at"}
    msg = box.messages[-1]
    assert msg["to"] == EDITOR_USER["email"] and "Restablece" in msg["subject"]
    (doc,) = token_docs(db, purpose="reset")
    delta = doc["expires_at"] - datetime.now(timezone.utc).replace(tzinfo=None)
    assert timedelta(hours=23, minutes=59) < delta <= timedelta(hours=24)
    assert "password" not in r.text.lower() or "hashed" not in r.text


def test_BE46_reset_only_for_active_users(ctx):
    c, h, db, ids, box = ctx
    body = create(c, h, ids)                                                 # invited
    r = c.post(f"/api/users/{uid(body)}/password-reset", headers=h)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "not_active"
    assert c.post("/api/users/6600000000000000000000ff/password-reset", headers=h).status_code == 404


def test_BE46_reset_mail_failure_is_502_with_stable_code(ctx):
    c, h, db, ids, box = ctx
    box.fail_with = MailError("mail_timeout")
    r = c.post(f"/api/users/{EDITOR_USER['_id']}/password-reset", headers=h)
    assert r.status_code == 502 and r.json()["detail"]["code"] == "mail_timeout"


def test_BE46_redeeming_a_reset_closes_open_sessions_and_replaces_the_password(ctx):
    c, h, db, ids, box = ctx
    old_session = {"Authorization": "Bearer " + jwt.encode(
        {"sub": EDITOR_USER["_id"], "iat": int(time.time()) - 3600, "exp": int(time.time()) + 600},
        settings.JWT_SECRET, algorithm="HS256")}
    assert c.get("/api/auth/me", headers=old_session).status_code == 200
    c.post(f"/api/users/{EDITOR_USER['_id']}/password-reset", headers=h)
    assert c.get("/api/auth/me", headers=old_session).status_code == 200           # hasta canjear, nada cambia
    assert c.post("/api/auth/login", json={"username": EDITOR_USER["email"], "password": "contrasena-anterior-muy-larga-1"}).status_code == 200
    assert redeem(c, box.last_token()).status_code == 204
    assert c.get("/api/auth/me", headers=old_session).status_code == 401
    assert c.post("/api/auth/login", json={"username": EDITOR_USER["email"], "password": "contrasena-anterior-muy-larga-1"}).status_code == 401
    assert c.post("/api/auth/login", json={"username": EDITOR_USER["email"], "password": GOOD_PASSWORD}).status_code == 200


def test_BE46_reset_link_of_a_user_disabled_meanwhile_is_rejected(ctx):
    c, h, db, ids, box = ctx
    c.post(f"/api/users/{EDITOR_USER['_id']}/password-reset", headers=h)
    token = box.last_token()
    c.post(f"/api/users/{EDITOR_USER['_id']}/disable", headers=h)
    assert redeem(c, token).status_code == 400


def test_BE46_invite_and_reset_tokens_are_independent(ctx):
    c, h, db, ids, box = ctx
    body = create(c, h, ids)
    invite = box.last_token()
    assert redeem(c, invite).status_code == 204
    c.post(f"/api/users/{uid(body)}/password-reset", headers=h)
    reset = box.last_token()
    assert reset != invite and len(token_docs(db, user_id=next(d["_id"] for d in db.users.docs if d["email"] == NEW_USER["email"]))) == 2
    assert redeem(c, invite).status_code == 400                                       # el de invitación ya se usó
    assert redeem(c, reset, "otra-contrasena-larga-y-unica-88").status_code == 204


# ── acceso a las rutas y auditoría ───────────────────────────────────────────
@pytest.mark.parametrize("path", ["invitation", "password-reset"])
def test_BE46_send_routes_are_iam_admin_only(ctx, path):
    c, h, db, ids, box = ctx
    url = f"/api/users/{EDITOR_USER['_id']}/{path}"
    assert c.post(url).status_code == 401
    assert c.post(url, headers=bearer_for(EDITOR_USER)).status_code == 403
    assert box.messages == []


def test_BE46_there_is_no_generic_send_endpoint(ctx):
    from app.main import app
    paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert not [p for p in paths if "mail" in p.lower() or "send" in p.lower() or "email" in p.lower()]


def test_BE46_password_set_and_reset_are_audited_without_secrets(ctx):
    c, h, db, ids, box = ctx
    body = create(c, h, ids)
    token = box.last_token()
    redeem(c, token)
    c.post(f"/api/users/{EDITOR_USER['_id']}/password-reset", headers=h)
    actions = [d["action"] for d in db.audit_log.docs]
    assert "user.password_set" in actions and "user.password_reset" in actions and "user.invite" in actions
    ps = next(d for d in db.audit_log.docs if d["action"] == "user.password_set")
    assert str(ps["actor_id"]) == uid(body) and ps["target_id"] == uid(body)
    assert GOOD_PASSWORD not in json.dumps(db.audit_log.docs, default=str)


# ── plantillas ────────────────────────────────────────────────────────────────
def test_BE46_templates_escape_user_data_and_contain_the_link():
    from app.auth.auth_entity import render_invitation, render_password_reset
    link = "https://gestion.slepllanquihue.cl/definir-contrasena#token=abc_DEF-123"
    for render in (render_invitation, render_password_reset):
        subject, html, text = render('<script>alert("x")</script>', link)
        assert "<script>" not in html and "&lt;script&gt;" in html
        assert link in html and link in text and "\n" not in subject
    _, html, _ = render_invitation("Ana", 'https://x.cl/"><img src=x onerror=alert(1)>#token=a')
    assert '"><img' not in html
