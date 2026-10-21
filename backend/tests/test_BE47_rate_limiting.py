"""
test_BE47_rate_limiting.py
━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: US-46 · Rate limiting de login, canje, reenvío y restablecimiento (ADR-014)

Verifica que:
  - 5 fallos por (cuenta + IP) dan 429 con Retry-After, aun con la contraseña correcta
  - cuenta inexistente, desactivada o con clave errónea cuentan y responden igual (no se enumeran cuentas)
  - el límite incluye la IP: un tercero no puede dejar inutilizable la cuenta de otro (sin DoS dirigido)
  - 30 fallos por IP bloquean el recorrido de muchas cuentas
  - un login correcto limpia el contador; la ventana vence sola
  - una cabecera X-Forwarded-For enviada por el cliente no evade el límite (la IP sale del servidor ASGI)
  - canje de enlaces: los canjes fallidos cuentan, los correctos y los 422 de política no
  - reenvío y restablecimiento: tope por destinatario y por administrador, y un envío bloqueado no manda correo
  - las claves guardadas no contienen correos, IP ni tokens en claro
  - si `rate_limits` falla, el login sigue funcionando (fail-open) y queda en el log
  - Gunicorn confía en X-Forwarded-For y el backend de producción no publica puerto
"""
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from pymongo.errors import DuplicateKeyError

from tests.conftest import ADMIN_USER, EDITOR_USER, bearer_for, prepare_org, run, user_with_password

ROOT = Path(__file__).resolve().parents[2]
PASSWORD = "contrasena-correcta-muy-larga-1"
OTHER_IP = ("203.0.113.7", 50000)


@pytest.fixture
def ctx(fake_db, mailbox):
    ids = prepare_org(fake_db, ADMIN_USER, user_with_password(EDITOR_USER, PASSWORD))
    from app.main import app
    return TestClient(app), bearer_for(ADMIN_USER), fake_db, ids, mailbox, app


def login(c, email=EDITOR_USER["email"], password="clave-incorrecta-cualquiera"):
    return c.post("/api/auth/login", json={"username": email, "password": password})


def fail_n(c, n, email=EDITOR_USER["email"]):
    return [login(c, email).status_code for _ in range(n)]


# ── login ─────────────────────────────────────────────────────────────────────
def test_BE47_fifth_failure_then_429_even_with_the_right_password(ctx):
    c, h, db, ids, box, app = ctx
    assert fail_n(c, 5) == [401] * 5
    r = login(c, password=PASSWORD)
    assert r.status_code == 429
    assert r.json()["detail"]["code"] == "rate_limited" and "Espera" in r.json()["detail"]["message"]
    assert 1 <= int(r.headers["retry-after"]) <= 15 * 60


def test_BE47_unknown_and_disabled_accounts_behave_exactly_like_real_ones(ctx):
    c, h, db, ids, box, app = ctx
    c.post(f"/api/users/{EDITOR_USER['_id']}/disable", headers=h)                   # desactivada
    results = {}
    for name, email in (("disabled", EDITOR_USER["email"]), ("unknown", "nadie@slepllanquihue.cl")):
        statuses = fail_n(TestClient(app, client=(f"198.51.100.{len(results) + 1}", 1)), 6, email)
        results[name] = statuses
    assert results["disabled"] == results["unknown"] == [401] * 5 + [429]
    r_known = login(TestClient(app, client=("198.51.100.20", 1)), EDITOR_USER["email"])
    assert r_known.status_code == 401 and set(r_known.json()) == {"detail"}


def test_BE47_a_third_party_cannot_lock_someone_elses_account(ctx):
    c, h, db, ids, box, app = ctx
    attacker = TestClient(app, client=OTHER_IP)
    assert fail_n(attacker, 6)[-1] == 429                                   # el atacante queda bloqueado...
    assert login(c, password=PASSWORD).status_code == 200                   # ...la persona real entra sin problema


def test_BE47_failures_from_many_accounts_hit_the_ip_limit(ctx):
    c, h, db, ids, box, app = ctx
    statuses = [login(c, f"cuenta{i}@slepllanquihue.cl").status_code for i in range(31)]
    assert statuses[:30] == [401] * 30 and statuses[30] == 429
    assert login(c, "otra-cuenta@slepllanquihue.cl").status_code == 429       # IP bloqueada para cualquier cuenta
    assert login(TestClient(app, client=OTHER_IP), password="x").status_code == 401


def test_BE47_successful_login_clears_the_account_counter(ctx):
    c, h, db, ids, box, app = ctx
    assert fail_n(c, 4) == [401] * 4
    assert login(c, password=PASSWORD).status_code == 200
    assert fail_n(c, 4) == [401] * 4                                          # empezó de cero
    assert login(c).status_code == 401 and login(c).status_code == 429


def test_BE47_window_expires_by_itself(ctx):
    c, h, db, ids, box, app = ctx
    fail_n(c, 5)
    assert login(c, password=PASSWORD).status_code == 429
    for d in db.rate_limits.docs:
        d["expires_at"] = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
    assert login(c, password=PASSWORD).status_code == 200
    fail_n(c, 1)
    assert max(d["count"] for d in db.rate_limits.docs) == 1                    # ventana nueva, contador nuevo


def test_BE47_forged_x_forwarded_for_does_not_evade_the_limit(ctx):
    c, h, db, ids, box, app = ctx
    statuses = [c.post("/api/auth/login", json={"username": EDITOR_USER["email"], "password": "mala"},
                       headers={"X-Forwarded-For": f"10.9.8.{i}", "X-Real-IP": f"10.9.7.{i}"}).status_code for i in range(6)]
    assert statuses == [401] * 5 + [429]


def test_BE47_login_form_shares_the_same_counters(ctx):
    c, h, db, ids, box, app = ctx
    for _ in range(5):
        c.post("/api/auth/login-form", data={"username": EDITOR_USER["email"], "password": "mala"})
    assert login(c, password=PASSWORD).status_code == 429
    assert c.post("/api/auth/login-form", data={"username": EDITOR_USER["email"], "password": PASSWORD}).status_code == 429


def test_BE47_a_blocked_request_does_not_pay_for_bcrypt(ctx):
    c, h, db, ids, box, app = ctx
    fail_n(c, 5)
    with patch("app.auth.auth_service.AuthService.authenticate_user", AsyncMock(side_effect=AssertionError("no debe llamarse"))):
        assert login(c, password=PASSWORD).status_code == 429


def test_BE47_stored_keys_contain_no_email_ip_or_password(ctx):
    c, h, db, ids, box, app = ctx
    fail_n(c, 2)
    dump = json.dumps(db.rate_limits.docs, default=str)
    assert db.rate_limits.docs
    for needle in (EDITOR_USER["email"], "testclient", "clave-incorrecta", "@"):
        assert needle not in dump


# ── canje de enlaces ──────────────────────────────────────────────────────────
def test_BE47_failed_redemptions_count_and_block_by_ip(ctx):
    c, h, db, ids, box, app = ctx
    body = c.post("/api/users", json={"first_name": "Ana", "last_name": "Pérez", "email": "ana.perez@slepllanquihue.cl",
                                      "is_slep_staff": True, "unit_id": ids["AF-TI"]}, headers=h).json()
    good = box.last_token()
    bad = lambda i: c.post("/api/auth/set-password", json={"token": f"{i:043d}", "password": "una-contrasena-larga-y-unica-77"})
    assert [bad(i).status_code for i in range(10)] == [400] * 10
    blocked = bad(11)
    assert blocked.status_code == 429 and "retry-after" in blocked.headers
    # bloqueado: ni siquiera el enlace bueno se prueba desde esa IP
    assert c.post("/api/auth/set-password", json={"token": good, "password": "una-contrasena-larga-y-unica-77"}).status_code == 429
    other = TestClient(c.app, client=OTHER_IP)
    assert other.post("/api/auth/set-password", json={"token": good, "password": "una-contrasena-larga-y-unica-77"}).status_code == 204


def test_BE47_successful_redemptions_and_policy_errors_do_not_count(ctx):
    c, h, db, ids, box, app = ctx
    c.post("/api/users", json={"first_name": "Ana", "last_name": "Pérez", "email": "ana.perez@slepllanquihue.cl",
                               "is_slep_staff": True, "unit_id": ids["AF-TI"]}, headers=h)
    token = box.last_token()
    for _ in range(15):                                                       # más que el límite
        assert c.post("/api/auth/set-password", json={"token": token, "password": "corta"}).status_code == 422
    assert c.post("/api/auth/set-password", json={"token": token, "password": "una-contrasena-larga-y-unica-77"}).status_code == 204


# ── envíos: reenvío y restablecimiento ────────────────────────────────────────
def invited(c, h, ids, n=0):
    r = c.post("/api/users", json={"first_name": "Ana", "last_name": "Pérez", "email": f"ana{n}.perez@slepllanquihue.cl",
                                   "is_slep_staff": True, "unit_id": ids["AF-TI"]}, headers=h)
    return r.json().get("_id") or r.json()["id"]


def test_BE47_resend_is_capped_per_recipient_and_a_blocked_send_sends_nothing(ctx):
    c, h, db, ids, box, app = ctx
    uid = invited(c, h, ids)
    before = len(box.messages)
    assert [c.post(f"/api/users/{uid}/invitation", headers=h).status_code for _ in range(5)] == [200] * 5
    assert len(box.messages) == before + 5
    r = c.post(f"/api/users/{uid}/invitation", headers=h)
    assert r.status_code == 429 and int(r.headers["retry-after"]) <= 3600
    assert len(box.messages) == before + 5                                    # el bloqueado no envió


def test_BE47_reset_and_resend_share_the_per_recipient_budget_of_their_own_user(ctx):
    c, h, db, ids, box, app = ctx
    assert [c.post(f"/api/users/{EDITOR_USER['_id']}/password-reset", headers=h).status_code for _ in range(5)] == [202] * 5
    assert c.post(f"/api/users/{EDITOR_USER['_id']}/password-reset", headers=h).status_code == 429
    uid = invited(c, h, ids, 1)                                               # otro destinatario: su propio cupo
    assert c.post(f"/api/users/{uid}/invitation", headers=h).status_code == 200


def test_BE47_per_admin_cap(ctx):
    c, h, db, ids, box, app = ctx
    from app.auth.auth_service import auth_service
    uid = invited(c, h, ids, 2)
    key = auth_service.rate_key("send-actor", ADMIN_USER["_id"])
    for _ in range(60):
        run(auth_service.rate_hit(key, 3600))
    assert c.post(f"/api/users/{uid}/invitation", headers=h).status_code == 429


def test_BE47_failed_sends_also_count(ctx):
    c, h, db, ids, box, app = ctx
    box.fail_with = RuntimeError("correo caído")
    from app.mail.mail_service import MailError
    box.fail_with = MailError("mail_send_failed")
    statuses = [c.post(f"/api/users/{EDITOR_USER['_id']}/password-reset", headers=h).status_code for _ in range(6)]
    assert statuses == [502] * 5 + [429]


# ── robustez y despliegue ─────────────────────────────────────────────────────
def test_BE47_counter_primitives(fake_db):
    from app.auth.auth_service import auth_service
    assert run(auth_service.rate_hit("k", 60)) == 1 and run(auth_service.rate_hit("k", 60)) == 2
    fake_db.rate_limits.docs[0]["expires_at"] = datetime(2020, 1, 1)
    assert run(auth_service.rate_hit("k", 60)) == 1                              # ventana vencida: se reabre
    run(auth_service.rate_clear("k"))
    assert fake_db.rate_limits.docs == []


def test_BE47_window_open_race_adds_to_the_other_workers_window(fake_db):
    from app.auth.auth_service import auth_service
    run(auth_service.rate_hit("k", 60))
    original = fake_db.rate_limits.find_one_and_update
    calls = {"n": 0}

    async def first_call_misses(filt, update, **kw):          # el worker A no ve la ventana (aún no existía para él)
        calls["n"] += 1
        return None if calls["n"] == 1 else await original(filt, update, **kw)

    with patch.object(fake_db.rate_limits, "find_one_and_update", first_call_misses), \
         patch.object(fake_db.rate_limits, "update_one", AsyncMock(side_effect=DuplicateKeyError("dup"))):
        assert run(auth_service.rate_hit("k", 60)) == 2


def test_BE47_unique_key_index(fake_db):
    prepare_org(fake_db)
    run(fake_db.rate_limits.insert_one({"key": "a", "count": 1, "expires_at": datetime(2030, 1, 1)}))
    with pytest.raises(DuplicateKeyError):
        run(fake_db.rate_limits.insert_one({"key": "a", "count": 1, "expires_at": datetime(2030, 1, 1)}))


def test_BE47_limiter_failure_fails_open_and_is_logged(ctx, caplog):
    c, h, db, ids, box, app = ctx
    boom = AsyncMock(side_effect=RuntimeError("rate_limits caída"))
    with patch.object(db.rate_limits, "find_one", boom), patch.object(db.rate_limits, "find_one_and_update", boom), \
         caplog.at_level(logging.ERROR, logger="auth"):
        assert login(c, password=PASSWORD).status_code == 200
        assert login(c).status_code == 401
    assert "rate_limits no disponible" in caplog.text


def test_BE47_prod_trusts_forwarded_for_but_backend_is_not_published():
    docker = (ROOT / "backend" / "Dockerfile.prod").read_text(encoding="utf-8")
    assert '"--forwarded-allow-ips"' in docker
    compose = (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
    backend = compose.split("  backend:")[1].split("  frontend:")[0]
    assert "expose:" in backend and "ports:" not in backend                     # condición de seguridad de "*"
    nginx = (ROOT / "frontend" / "nginx.conf").read_text(encoding="utf-8")
    assert "proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for" in nginx
