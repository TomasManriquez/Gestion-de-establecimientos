"""
test_BE52_jwt_required_claims.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: SEC-2 · El token debe traer exp, iat y sub; algoritmo fijado

Verifica que (todo con el mismo 401):
  - un token firmado sin `exp`, sin `iat` o sin `sub` se rechaza
  - `alg: none` y un token HS512 firmado con el secreto correcto se rechazan
  - un token completo y válido sigue sirviendo (el leeway de D28 se mantiene)
"""
import base64
import json
import time
from datetime import datetime, timedelta, timezone
import jwt
import pytest
from fastapi.testclient import TestClient
from app.config import settings
from tests.conftest import ADMIN_USER, seed_users

UID = ADMIN_USER["_id"]


def me(headers):
    from app.main import app
    return TestClient(app).get("/api/auth/me", headers={"Authorization": "Bearer " + headers})


def full(**overrides):
    body = {"sub": UID, "iat": int(time.time()), "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
    body.update(overrides)
    return {k: v for k, v in body.items() if v is not None}


def sign(body, alg="HS256"):
    return jwt.encode(body, settings.JWT_SECRET, algorithm=alg)


def test_BE52_complete_token_accepted(fake_db):
    seed_users(fake_db, ADMIN_USER)
    assert me(sign(full())).status_code == 200


def test_BE52_token_issued_slightly_in_the_future_accepted(fake_db):
    """Reloj de WSL2 (D28): el leeway de 10 s sigue vigente."""
    seed_users(fake_db, ADMIN_USER)
    assert me(sign(full(iat=int(time.time()) + 5))).status_code == 200


@pytest.mark.parametrize("missing", ["exp", "iat", "sub"])
def test_BE52_missing_required_claim_rejected(fake_db, missing):
    seed_users(fake_db, ADMIN_USER)
    r = me(sign(full(**{missing: None})))
    assert r.status_code == 401 and r.json() == {"detail": "Could not validate credentials"}


def test_BE52_alg_none_rejected(fake_db):
    seed_users(fake_db, ADMIN_USER)
    b64 = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    body = full(exp=int(time.time()) + 300)
    assert me(f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64(body)}.").status_code == 401


def test_BE52_hs512_token_rejected_even_with_the_right_secret(fake_db):
    seed_users(fake_db, ADMIN_USER)
    assert me(sign(full(), alg="HS512")).status_code == 401
